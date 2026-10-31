// Wi-Fi transport fork of the existing GPIO21 diagnostic. No firmware upload performed.
#include <Arduino.h>
#include "wifi_link.h"
#define Serial Diag
#include "driver/uart.h"
#include "driver/gpio.h"
#include "soc/gpio_struct.h"
#include "soc/gpio_sig_map.h"
#include "esp_rom_gpio.h"

// ESP UART1 is radar UART0 (control). ESP UART2 is radar UART1 (data).
constexpr gpio_num_t DATA_RX_PIN = GPIO_NUM_21;
HardwareSerial Control(1);
QueueHandle_t events;
portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
struct Stats {
  uint32_t bytes, fifoOverflow, bufferFull, frameError, parityError, breaks, readError;
  uint32_t controlErrors;
  uint8_t sample[64];
  uint32_t sampleSize;
} stats = {};
uint8_t *captureBuffer = nullptr;
const uint32_t captureCapacity = 524288;
uint32_t captureStored = 0, captureDropped = 0;
bool captureEnabled = true;
uint32_t dataBaud = 1000000;
uint32_t controlBytes = 0, deadline = 0, versionBaseline = 0;
bool ready = false;
String responseLine, hostLine;
bool lineTruncated = false, versionPending = false, versionVerified = false;

void receiveData(void *) {
  uint8_t buffer[2048];
  for (;;) {
    uart_event_t event;
    while (xQueueReceive(events, &event, 0) == pdTRUE) {
      portENTER_CRITICAL(&lock);
      switch (event.type) {
        case UART_FIFO_OVF: stats.fifoOverflow++; break;
        case UART_BUFFER_FULL: stats.bufferFull++; break;
        case UART_FRAME_ERR: stats.frameError++; break;
        case UART_PARITY_ERR: stats.parityError++; break;
        case UART_BREAK: stats.breaks++; break;
        default: break;
      }
      portEXIT_CRITICAL(&lock);
    }
    int n = uart_read_bytes(UART_NUM_2, buffer, sizeof(buffer), pdMS_TO_TICKS(2));
    portENTER_CRITICAL(&lock);
    if (n < 0) stats.readError++;
    else {
      stats.bytes += n;
      if(captureEnabled && captureBuffer) {
        uint32_t keep = min((uint32_t)n, captureCapacity - captureStored);
        memcpy(captureBuffer + captureStored, buffer, keep);
        captureStored += keep; captureDropped += n - keep;
      }
      for (int i = 0; i < n && stats.sampleSize < sizeof(stats.sample); i++)
        stats.sample[stats.sampleSize++] = buffer[i];
    }
    portEXIT_CRITICAL(&lock);
    if(n>0)enqueueRadarBytes(buffer,n);
  }
}

void status() {
  Stats s;
  portENTER_CRITICAL(&lock); s = stats; portEXIT_CRITICAL(&lock);
  Serial.printf("\n[STATUS ms=%lu] control_bytes=%lu data_bytes=%lu fifo_overflow=%lu buffer_full=%lu frame_error=%lu parity_error=%lu breaks=%lu read_error=%lu control_errors=%lu version_verified=%u\n",
    millis(), controlBytes, s.bytes, s.fifoOverflow, s.bufferFull, s.frameError,
    s.parityError, s.breaks, s.readError, s.controlErrors, versionVerified);
  Serial.printf("[DATA first_%lu_bytes]", s.sampleSize);
  for (uint32_t i=0; i<s.sampleSize; i++) Serial.printf(" %02X", s.sample[i]);
  Serial.println();
}

void mapPins() {
  Serial.printf("[MAP] U1RX=%08lx U2RX=%08lx OUT17=%08lx OUT21=%08lx baud=%lu stored=%lu dropped=%lu\n",
    GPIO.func_in_sel_cfg[U1RXD_IN_IDX].val, GPIO.func_in_sel_cfg[U2RXD_IN_IDX].val,
    GPIO.func_out_sel_cfg[17].val, GPIO.func_out_sel_cfg[DATA_RX_PIN].val, dataBaud, captureStored, captureDropped);
  gpio_dump_io_configuration(stdout, (1ULL<<16)|(1ULL<<17)|(1ULL<<DATA_RX_PIN));
}
void command(String command) {
  command.trim();
  if (command == "CONTROL_MATRIX") {
    gpio_reset_pin(GPIO_NUM_16);gpio_set_direction(GPIO_NUM_16,GPIO_MODE_INPUT);gpio_pullup_en(GPIO_NUM_16);
    esp_rom_gpio_connect_in_signal(16,U1RXD_IN_IDX,false);
    gpio_reset_pin(GPIO_NUM_17);gpio_set_direction(GPIO_NUM_17,GPIO_MODE_OUTPUT);
    esp_rom_gpio_connect_out_signal(17,U1TXD_OUT_IDX,false,false);
    uart_set_loop_back(UART_NUM_1,false);
    Serial.println("[CONTROL_MATRIX]");mapPins();return;
  }
  if (command == "TX_HIZ") {
    gpio_reset_pin(GPIO_NUM_17);gpio_set_direction(GPIO_NUM_17,GPIO_MODE_INPUT);
    Serial.println("[TX_HIZ] GPIO17 disconnected from UART TX; commands cannot reach radar");mapPins();return;
  }
  if (command == "MAP") { mapPins(); return; }
  if (command == "PIN_FIX") {
    gpio_reset_pin(DATA_RX_PIN);
    gpio_set_direction(DATA_RX_PIN, GPIO_MODE_INPUT);
    gpio_pullup_en(DATA_RX_PIN);
    esp_err_t e=uart_set_pin(UART_NUM_2, -1,DATA_RX_PIN,-1,-1);
    uart_set_loop_back(UART_NUM_2, false);
    Serial.printf("[PIN_FIX] result=%d\n",e); mapPins(); return;
  }
  if (command == "DATA_CONST_HIGH") {
    esp_rom_gpio_connect_in_signal(0x38,U2RXD_IN_IDX,false);
    Serial.println("[DATA_CONST_HIGH]");mapPins();return;
  }
  if (command.startsWith("DATA_BAUD ")) {
    uint32_t baud=command.substring(10).toInt();
    if(baud!=115200 && baud!=1000000 && baud!=460800) {Serial.println("[ERROR] unsupported test baud");return;}
    esp_err_t e=uart_set_baudrate(UART_NUM_2,baud); if(e==ESP_OK)dataBaud=baud;
    Serial.printf("[DATA_BAUD] %lu result=%d\n",baud,e);return;
  }
  if (command == "CAPTURE_RESET") {
    portENTER_CRITICAL(&lock);stats={};captureStored=0;captureDropped=0;captureEnabled=true;portEXIT_CRITICAL(&lock);
    Serial.println("[CAPTURE_RESET]");return;
  }
  if (command == "DUMP") { Serial.println("[ERROR] Binary dump requires the USB capture firmware"); return; }
  if (command == "STATUS") { status(); return; }
  if (command == "INFO") { mapPins();
    Serial.printf("[INFO] ready=%u chip=%s flash=%lu psram=%lu control=RX16/TX17/115200 data=RX21/1000000 flow=none\n",
      ready, ESP.getChipModel(), ESP.getFlashChipSize(), ESP.getPsramSize());
    return;
  }
  if (!ready) { Serial.println("[ERROR] UART initialization failed"); return; }
  if (command == "CONFIRM_VERSION") {
    // Host operator must inspect the received firmware identity before confirming.
    if (!versionPending || controlBytes <= versionBaseline) { Serial.println("[ERROR] No version response received"); return; }
    versionVerified = true;
    Serial.println("[HOST] Radar version response reviewed and confirmed");
    return;
  }
  if (!command.startsWith("mmwc ")) { Serial.println("[ERROR] Expected mmwc command or STATUS"); return; }
  if (command == "mmwc version") { versionPending = true; versionVerified = false; versionBaseline = controlBytes; }
  if (command.startsWith("mmwc start")) {
    if (wifiFault) { Serial.println("[ERROR] Restart ESP after Wi-Fi log fault before scanning"); return; }
    if (!versionVerified) { Serial.println("[ERROR] Start blocked: verify radar version first"); return; }
    deadline = millis() + 25000;
  }
  Serial.printf("[TX] %s\n", command.c_str());
  Control.print(command); Control.print("\r\n");
}

void setup() {
  beginWifiLink();
  Serial.begin(115200);
  if (HAVEN_CSI_ONLY) {
    ready = true;
    diagnosticsReady = true;
    Serial.println("HAVEN_CSI_WIFI_v1: CSI only; radar GPIOs not initialized");
    return;
  }
  captureBuffer=(uint8_t*)ps_malloc(captureCapacity);
  Control.setRxBufferSize(8192);
  Control.begin(115200, SERIAL_8N1, 16, 17);
  Control.onReceiveError([](hardwareSerial_error_t) {
    portENTER_CRITICAL(&lock); stats.controlErrors++; portEXIT_CRITICAL(&lock);
  });
  uart_set_hw_flow_ctrl(UART_NUM_1, UART_HW_FLOWCTRL_DISABLE, 0);
  uart_config_t config = {};
  config.baud_rate = 1000000; config.data_bits = UART_DATA_8_BITS;
  config.parity = UART_PARITY_DISABLE; config.stop_bits = UART_STOP_BITS_1;
  config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE; config.source_clk = UART_SCLK_DEFAULT;
  esp_err_t a = uart_param_config(UART_NUM_2, &config);
  // No TX, RTS, or CTS GPIO is assigned for the data UART.
  esp_err_t b = uart_set_pin(UART_NUM_2, UART_PIN_NO_CHANGE, DATA_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
  esp_err_t c = uart_driver_install(UART_NUM_2, 32768, 0, 64, &events, 0);
  ready = captureBuffer && a == ESP_OK && b == ESP_OK && c == ESP_OK;
  if (ready) ready = xTaskCreatePinnedToCore(receiveData, "radar_rx", 4096, nullptr, 3, nullptr, 0) == pdPASS;
  delay(1500);
  Serial.printf("\nRD60_CAPTURE_GPIO21 v1 ready=%u config=%d pins=%d driver=%d\n", ready,a,b,c);
  Serial.printf("chip=%s flash=%lu psram=%lu\n", ESP.getChipModel(), ESP.getFlashChipSize(), ESP.getPsramSize());
  Serial.println("control: UART1 RX16 TX17 115200 8N1; data: UART2 RX21 1000000 8N1; flow=none");
  Serial.println("Data ring=32768; first 64 bytes only; UART events counted; no packet decoding.");
  Serial.println("Send mmwc version; inspect actual reply; send CONFIRM_VERSION before finite scan.");
  diagnosticsReady = true;
}

void loop() {
  static uint32_t wifiFaultSince = 0;
  if (HAVEN_CSI_ONLY) {
    if (linkOverflow && !wifiFaultSince) wifiFaultSince = millis();
    if (wifiFaultSince && millis() - wifiFaultSince >= 10000) ESP.restart();
    delay(10);
    return;
  }
  char queued[129];
  if (linkOverflow && !wifiFault) {
    linkOverflow = false;
    wifiFault = true;
    wifiFaultSince = millis();
    deadline = 0;
    command("mmwc stop");
    Serial.println("[ERROR] Wi-Fi logs lost or stale; reconnect before further scanning");
  }
  // The stop above runs before a new boot/session. Never resume an old scan.
  if (wifiFault && millis() - wifiFaultSince >= 10000) ESP.restart();
  while (incomingCommands && xQueueReceive(incomingCommands, queued, 0) == pdTRUE) command(String(queued));
  while (Control.available()) {
    char ch = Control.read(); controlBytes++;
    if (ch == '\n' || ch == '\r') {
      if (responseLine.length()) {
        Serial.printf("[RADAR] %s%s\n",responseLine.c_str(),lineTruncated?" [LINE TRUNCATED]":"");
        responseLine = ""; lineTruncated = false;
      }
    } else if (responseLine.length() < 512) responseLine += ch;
    else lineTruncated = true;
  }
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') { if (hostLine.length()) command(hostLine); hostLine=""; }
    else if (hostLine.length() < 128) hostLine += ch;
    else { hostLine=""; Serial.println("[ERROR] Host command too long"); }
  }
  if (deadline && (int32_t)(millis()-deadline)>=0) {
    deadline=0; command("mmwc stop"); Serial.println("[WATCHDOG] Stop sent; inspect radar acknowledgement");
  }
  static uint32_t last=0;
  if (millis()-last>=1000) { last=millis(); status(); }
  delay(1);
}
