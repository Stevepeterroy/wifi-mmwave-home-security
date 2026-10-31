#pragma once
// Copy to secrets.h and fill locally. Do not commit secrets.h.
#define HAVEN_WIFI_SSID ""
#define HAVEN_WIFI_PASSWORD ""
#define HAVEN_MODULE_ID "rd60-1"
#define HAVEN_DEVICE_TOKEN ""
#define HAVEN_EXCHANGE_URL "https://your-haven-host:8768/api/wifi/exchange"
// PEM root CA that validates the Haven hostname. Never use setInsecure().
#define HAVEN_ROOT_CA ""

// Set to 1 to stream CSI without initializing or requiring the radar UARTs.
#define HAVEN_CSI_ONLY 0
