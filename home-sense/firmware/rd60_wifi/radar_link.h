#pragma once
// Bounded evidence transport; does not decode RD-60 packets.
struct RadarChunk {uint32_t sequence, ms; uint16_t length; uint8_t bytes[512];};
static QueueHandle_t radarQueue;
static std::atomic<uint32_t> radarSequence{0},radarDropped{0};
static void enqueueRadarBytes(const uint8_t* bytes,size_t length) {
  if(!radarQueue)return;
  for(size_t offset=0;offset<length;offset+=512) {
    RadarChunk c={};c.sequence=++radarSequence;c.ms=millis();c.length=min((size_t)512,length-offset);
    memcpy(c.bytes,bytes+offset,c.length);
    if(xQueueSend(radarQueue,&c,0)!=pdTRUE)radarDropped+=c.length;
  }
}
static cJSON* radarBatch() {
  cJSON* batch=cJSON_CreateArray();RadarChunk chunk;
  for(int n=0;n<4 && radarQueue && xQueueReceive(radarQueue,&chunk,0)==pdTRUE;n++) {
    if(millis()-chunk.ms>1000){radarDropped+=chunk.length;continue;}
    unsigned char encoded[685];size_t size=0;
    if(mbedtls_base64_encode(encoded,sizeof(encoded)-1,&size,chunk.bytes,chunk.length)!=0){radarDropped+=chunk.length;continue;}
    encoded[size]=0;
    cJSON* item=cJSON_CreateObject();cJSON_AddNumberToObject(item,"sequence",chunk.sequence);
    cJSON_AddNumberToObject(item,"device_ms",chunk.ms);cJSON_AddNumberToObject(item,"age_ms",millis()-chunk.ms);
    cJSON_AddStringToObject(item,"data",(const char*)encoded);cJSON_AddItemToArray(batch,item);
  }
  return batch;
}
