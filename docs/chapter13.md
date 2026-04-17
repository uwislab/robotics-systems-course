---
number headings: first-level 2, start-at 13
---

## 13 第 13 章 实验一：STM32 基础外设实验

> 本实验引导学生在 PicSimlab 仿真环境或实际 Blue Pill 硬件上完成 GPIO、定时器和串口三个基础实验，巩固第 3~6 章的理论知识。

### 13.1 实验目的

1. 掌握 CubeMX 工程创建和引脚配置流程
2. 熟练使用 GPIO 控制 LED 和读取按键
3. 理解定时器中断和 PWM 输出的配置方法
4. 掌握 UART 串口收发编程

### 13.2 实验环境

**表 13-1** 实验环境配置
<!-- tab:ch13-1 实验环境配置 -->

| 项目 | 方案 A（仿真） | 方案 B（实物） |
|------|--------------|--------------|
| 开发板 | PicSimlab Blue Pill 虚拟板 | STM32F103C8T6 Blue Pill |
| IDE | CubeIDE 1.14+ | CubeIDE 1.14+ |
| 调试器 | PicSimlab GDB Server | ST-Link V2 |
| 串口工具 | PicSimlab UART TCP Bridge | USB-TTL + 串口助手 |

### 13.3 实验一：GPIO — LED 与按键

#### 13.3.1 实验内容

1. 配置 PC13 为推挽输出，控制板载 LED 闪烁（1Hz）
2. 配置 PA0 为上拉输入，读取按键状态
3. 实现：按键按下时 LED 常亮，松开时 LED 闪烁

#### 13.3.2 CubeMX 配置步骤

1. 新建 STM32F103C8Tx 工程
2. PC13 → GPIO_Output（推挽、无上下拉、低速）
3. PA0 → GPIO_Input（上拉）
4. 生成代码，选择 CubeIDE 工具链

#### 13.3.3 参考代码

```c
int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();

    while (1) {
        if (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0) == GPIO_PIN_RESET) {
            /* 按键按下（低电平有效） → LED 常亮 */
            HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
        } else {
            /* 按键松开 → LED 闪烁 */
            HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
            HAL_Delay(500);
        }
    }
}
```

#### 13.3.4 思考与拓展

- 按键抖动会导致什么问题？如何进行软件消抖？
- 如何用外部中断（EXTI）代替轮询读取按键？

---

### 13.4 实验二：定时器 — PWM 呼吸灯

#### 13.4.1 实验内容

1. 配置 TIM2_CH1 输出 1kHz PWM，控制外接 LED（PA0）
2. 在主循环中逐步改变占空比，实现呼吸灯效果
3. 测量 PWM 波形，验证频率和占空比正确

#### 13.4.2 CubeMX 配置

- TIM2 → Clock Source: Internal Clock
- Channel 1 → PWM Generation CH1
- PSC = 71（72MHz / 72 = 1MHz 计数频率）
- ARR = 999（1MHz / 1000 = 1kHz PWM 频率）
- PA0 → TIM2_CH1

#### 13.4.3 参考代码

```c
int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_TIM2_Init();

    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);

    while (1) {
        /* 渐亮 */
        for (uint16_t d = 0; d <= 999; d += 5) {
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, d);
            HAL_Delay(5);
        }
        /* 渐暗 */
        for (uint16_t d = 999; d > 0; d -= 5) {
            __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, d);
            HAL_Delay(5);
        }
    }
}
```

---

### 13.5 实验三：UART 串口回显

#### 13.5.1 实验内容

1. 配置 USART1（PA9/PA10，115200-8-N-1）
2. 接收 PC 发送的数据，原样回传并在 OLED 或串口助手上显示
3. 定义简单指令协议：发送 `LED_ON` 点亮 LED，`LED_OFF` 熄灭 LED

#### 13.5.2 参考代码

```c
uint8_t rx_byte;

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        /* 回显 */
        HAL_UART_Transmit(&huart1, &rx_byte, 1, 10);
        /* 继续接收 */
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_USART1_UART_Init();
    MX_GPIO_Init();

    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);

    char *msg = "UART Echo Ready\r\n";
    HAL_UART_Transmit(&huart1, (uint8_t *)msg, strlen(msg), 100);

    while (1) {
        /* 主循环空闲，数据处理在中断回调中完成 */
    }
}
```

---

### 13.6 实验报告要求

**表 13-2** 实验报告内容与评分
<!-- tab:ch13-2 实验报告内容与评分 -->

| 内容 | 分值 | 要求 |
|------|:----:|------|
| CubeMX 配置截图 | 20% | 包含引脚配置和时钟树 |
| 核心代码及注释 | 30% | 注释清晰，逻辑正确 |
| 运行结果截图/录屏 | 20% | 波形/串口输出的实际截图 |
| 问题分析 | 15% | 记录调试过程中遇到的问题及解决方法 |
| 拓展思考 | 15% | 回答思考题或完成拓展任务 |