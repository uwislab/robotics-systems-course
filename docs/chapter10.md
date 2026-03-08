# 第10章 嵌入式系统与互联网：ESP8266/ESP32 的蓝牙与 WiFi 应用，NAT 穿越与 MQTT

本章核心内容：基于 ESP8266 与 ESP32 的无线连接（WiFi、蓝牙 BLE/BT）实现方法、嵌入式设备如何安全接入互联网、常见 NAT 穿越策略（用于远程控制）、以及 MQTT 在物联网中的工程实践与安全应用。面向研究生，强调理论与工程实践结合，提供架构图、时序图、实现要点、核心代码片段与安全/性能考量。

学习目标：
- 掌握 ESP8266/ESP32 的网络与蓝牙能力差异及选型依据；
- 能够设计并实现基于 MQTT 的远程控制方案，并理解为何该方法可规避 NAT 问题；
- 理解 NAT 穿越常见技术（反向连接、STUN/TURN、WebSocket/HTTP 翻转、VPN/SSH 隧道）在嵌入式场景中的优缺点；
- 能在嵌入式设备上实现安全的 MQTT 客户端（TLS、认证、LWT、QoS）、并完成基本故障与性能工程化考虑。

---

## 10.1 ESP8266 与 ESP32 特性对比与选型

表格：ESP8266 vs ESP32（简要对比）

| 特性 | ESP8266 | ESP32 |
|---|---:|---|
| 内核 | 单核 Tensilica | 双核/单核 Xtensa，含低功耗协处理器 |
| 蓝牙 | 无 | 支持 BLE & Classic (ESP32) |
| WiFi | 802.11 b/g/n | 802.11 b/g/n (更好的并发与吞吐) |
| 硬件加密 | 较弱 | 硬件加密加速（AES/SSL） |
| 外设 | 较少 | 丰富（ADC, DAC, I2S, SPI, UART 等） |
| 适用场景 | 低成本 WiFi 设备、简单传感器节点 | 需要蓝牙、多任务或更高性能的应用 |

选型建议：对蓝牙或更复杂并发需求选择 ESP32；对成本敏感且只需 WiFi 的简单传感器可选 ESP8266。

---

## 10.2 WiFi 应用实践（连接、DHCP、mDNS）

关键点：
- 建立稳定的 WiFi STA 连接，处理断连重连策略（指数退避、最大重试次数）；
- 使用 mDNS/UPnP 简化局域网内设备发现；
- 使用 DHCP 静态租约或静态 IP（对远程访问有帮助，但不能穿透 NAT 本质）。

示意代码（ESP8266 Arduino WiFiSTA）:

```cpp
#include <ESP8266WiFi.h>

const char* ssid = "ssid";
const char* pass = "password";

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, pass);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
    delay(200);
    Serial.print('.');
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(WiFi.localIP());
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    // 简单重连策略
    WiFi.disconnect();
    WiFi.begin(ssid, pass);
    delay(1000);
  }
  // 业务逻辑
}
```

---

## 10.3 蓝牙应用简介（ESP32）

关键点：
- ESP32 支持 BLE GATT 服务与 Classic SPP；研究生需理解 BLE 的低功耗连接模型与 ATT/GATT 抽象；
- 在嵌入式设计中，常用 BLE 作为短距离配置/调试通道（如 WiFi 配置）或低速传输数据。 

示意：BLE 广告与 GATT 服务交互（Mermaid）

```mermaid
sequenceDiagram
  participant Peripheral as ESP32 (Peripheral)
  participant Central as 手机/App (Central)
  Peripheral->>Central: 广播广告 (Adv)
  Central->>Peripheral: 连接请求
  Central->>Peripheral: 发现服务 (GATT Discovery)
  Central->>Peripheral: 写特征 -> 配置 WiFi
```

代码提示（ESP-IDF/NimBLE）: 实现时推荐使用 ESP-IDF 提供的 NimBLE/GATTS 示例，关注回连与断开处理、MTU 协商及安全配对策略。

---

## 10.4 NAT 穿越与远程控制策略

问题背景：大多数家庭/企业网络使用 NAT，设备位于私有地址后无法被互联网上的控制端直接发起 TCP 连接。常用解决策略：

1) 使用云中继（推荐）——设备主动发起到云服务器的长连接（MQTT/TCP/WebSocket），控制端通过云服务器下发命令；
2) 反向隧道（Reverse SSH / Reverse TCP）——设备建立反向代理隧道到公网服务器；
3) P2P 打洞（STUN/ICE）——在可行的 NAT 类型下让两端直接建立 UDP/TCP 连接；
4) VPN（OpenVPN / WireGuard）——将设备与控制端加入同一虚拟网络，适用于对延迟有一定要求且能管理隧道的场景。

对嵌入式设备的建议：首选云中继（MQTT/WebSocket）因实现简单、可靠性高；对高带宽或低延迟需求，考虑 VPN 或 P2P（但 P2P 受限于 NAT 类型）。

架构示意图（云中继 + MQTT）

```mermaid
flowchart LR
  Device[ESP device (私网)] -->|TLS| Broker[云端 MQTT Broker (公网)]
  Controller[控制端 (App/Server)] -->|TLS| Broker
  Broker -->|转发| Device
```

时序（基于 MQTT 的远程控制）

```mermaid
sequenceDiagram
  participant D as 设备
  participant B as MQTT Broker
  participant C as 控制端
  D->>B: 建立 TLS 连接并订阅 control/device/{id}
  C->>B: 发布消息到 control/device/{id}
  B->>D: 转发消息
  D->>D: 解析命令并执行
  D->>B: 发布状态到 status/device/{id}
  B->>C: 转发状态
```

---

## 10.5 MQTT 在嵌入式的应用实践

关键概念：主题（Topic）、QoS（0/1/2）、保留消息（Retain）、遗嘱（Last Will, LWT）、会话持久化（Clean Session）、保持心跳（Keep Alive）。

安全建议：
- 使用 TLS（最好带服务器证书验证）保护 MQTT 通信；
- 使用客户端证书或强认证机制，避免弱口令；
- 对控制主题进行授权与细粒度访问控制（ACL）；
- 合理设置 QoS 与重试策略以平衡延迟与可靠性。

示例（ESP8266 + PubSubClient）：

```cpp
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

const char* ssid = "...";
const char* pass = "...";
const char* mqtt_host = "broker.example.com";
const int mqtt_port = 8883; // TLS

WiFiClientSecure secureClient;
PubSubClient client(secureClient);

void callback(char* topic, byte* payload, unsigned int length) {
  // 处理控制命令
}

void connectMQTT() {
  secureClient.setCACert(ca_cert_pem);
  while (!client.connected()) {
    if (client.connect("device-001")) {
      client.subscribe("control/device/device-001");
      client.publish("status/device/device-001", "online", true);
    } else {
      delay(2000);
    }
  }
}

void setup() {
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) delay(100);
  client.setServer(mqtt_host, mqtt_port);
  client.setCallback(callback);
  connectMQTT();
}

void loop() {
  if (!client.connected()) connectMQTT();
  client.loop();
  // 心跳 / 状态发布
  static unsigned long t0 = 0;
  if (millis() - t0 > 5000) {
    client.publish("status/device/device-001", "ok");
    t0 = millis();
  }
}
```

QoS 与可靠性：
- QoS0（最多一次）适合非关键 telemetry；
- QoS1（至少一次）适合命令类消息，可配合幂等处理避免重复执行；
- QoS2（仅一次）开销最大，嵌入式场景较少使用。

---

## 10.6 NAT 穿越工程实现建议（细化）

1) 使用云中继（MQTT 或 WebSocket）：设备主动发起 TLS 连接到云端 MQTT Broker，控制端通过 broker 下发指令。优势：穿透 NAT、易于扩展；劣势：引入中继延迟与运营成本。
2) 若需 P2P：使用 STUN/ICE 做打洞并在必要时回退到 TURN（转发服务器）。注意：STUN 成功率受 NAT 类型影响；TURN 对嵌入式设备增加带宽成本。
3) 反向隧道：设备用 SSH/Reverse TCP 建立隧道到运维服务器，控制端通过该服务器访问设备。适合可部署运维场景但需管理隧道安全性。

工程落地注意：连接稳定性（重连与保活）、带宽限制（避免大量日志上云）、隐私与访问控制、固件升级通道安全（OTA 使用签名与完整性校验）。

---

## 10.7 工程示例：ESP32 使用 MQTT 做远程控制与固件升级

架构要点：
- 设备与 Broker 使用 TLS，Broker 验证客户端证书或用户名/密码；
- 设备订阅 control/{id}，发布 status/{id} 与 ota/{id} 主题；
- OTA 通过 chunked 文件发布（或使用 HTTP(S) 下载并验证签名）。

示意流程（OTA via MQTT）

```mermaid
sequenceDiagram
  participant Dev as 开发者发布工具
  participant B as Broker
  participant D as Device
  Dev->>B: 发布 OTA chunk 到 ota/device-001
  B->>D: 转发 chunk
  D->>D: 写入 flash 暂存
  D->>B: 发布 ota_ack
  D->>D: 验证签名并重启到新固件
```

核心实现提示：
- 避免在 MQTT 消息内嵌入大 payload，使用分块并带序号与签名；
- 使用双分区 OTA 与完整性校验（签名 + 哈希）；
- 发布固件时确保 QoS 与重试策略，以保证每块可靠到达或通知失败重试。

---

## 10.8 安全与隐私考量

- 使用 TLS（至少 TLS1.2）并验证服务端证书；对极高安全需求使用双向 TLS（客户端证书）；
- 对控制主题启用 ACL 与审计日志，避免未经授权的命令；
- 频繁更新依赖库与固件以修补已知漏洞；
- 最小化设备暴露的调试接口（串口、JTAG）并在发布固件时禁用。

---

## 10.9 本章测试题（mkdocs-quiz 格式）

::: quiz

# 单项选择题（1 分）

Q1: 在大多数家庭 NAT 场景下，下述哪种方法最可靠地实现远程控制（不要求 P2P 低延迟）？
- A: 直接 TCP 连接到设备私有 IP
- B: 设备主动连接到云端 MQTT Broker 并订阅控制主题
- C: 通过 UDP 打洞（STUN）保证 100% 成功
- D: 仅依赖局域网内 mDNS 发现

Answer: B
解析: 设备主动建立到公网 Broker 的连接可穿透 NAT 并能稳定转发控制消息，UDP 打洞受限于 NAT 类型不保证成功；直接连接私有 IP 无法跨 NAT。

---

# 多项选择题（2 分）

Q2: 关于 MQTT 在嵌入式设备上的使用，下列哪些做法是推荐且有助于提升安全性与可靠性？（多选）
- A: 使用 TLS 加密传输
- B: 在控制主题使用 QoS0
- C: 使用 LWT 提示离线状态
- D: 将固件通过未经签名的 MQTT 消息直接执行更新

Answer: A;C
解析: TLS 与 LWT 是推荐做法；控制主题通常至少用 QoS1 保证命令到达，固件更新必须签名校验以保证安全性。

---

# 简答题（6 分）

Q3: 说明 STUN 与 TURN 在 NAT 穿越流程中的作用与差别，并简述为什么 TURN 在嵌入式业务中成本较高。

Answer: STUN 用于探测公共地址并帮助两端在多数对称 NAT 以外的场景打洞实现 P2P；TURN 在 P2P 无法建立时充当中继，转发实际流量。TURN 增加带宽占用与服务器成本，嵌入式设备若流量较大或常驻连接将带来可观的运营成本，因此一般优先使用 Broker 中继或 VPN。

---

# 综合应用题（10 分）

Q4: 设计一套基于 ESP32 的远程控制方案，要求能在家庭 NAT 后安全控制设备、支持 OTA 更新并在网络断连时保证可恢复性。请给出总体架构、关键协议选择与安全措施（不超过 300 字）。

Answer 要点示例：
- 架构：设备作为 MQTT 客户端通过 TLS 连接至云端 Broker；控制端同样与 Broker 通信；OTA 使用分块下载并签名验证；在设备断线时使用 LWT 通知并在重连后采用增量重试。安全措施：TLS（服务端证书与服务器验证）、设备认证（证书或强令牌）、ACL 控制主题访问、固件签名与分区回滚；连接健壮性：带重试与退避策略、心跳与 Watchdog。 

:::

---

本章参考资料：ESP-IDF/ESP8266 SDK 文档、MQTT 协议规范 (OASIS)、STUN/TURN/ICE RFC 文档与物联网安全最佳实践。
