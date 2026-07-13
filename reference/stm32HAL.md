# stm32CubeMXIDE使用
- `Alt+/`获取代码提示
- 右键设置标签，设置后无需进行引脚编号配置，会直接显示为设置的标签
- 在`begin`和`end`之间写代码，否则会被删掉
- System Core→Debug:Serial Wire→SysTink
- Project Manager→Code Generator→Generate….c/.h为每个外设设置.c和.h文件
# GPIO的输出模式：
```c
HAL_GPIO_WritePin(GPIOx, GPIO_Pin, PinState)//写入GPIO，GPIO_PIN_SET拉高，RESET拉低
HAL_Delay(Delay)//延迟
HAL_GPIO_ReadPin(GPIOx, GPIO_Pin)//检测GPIO状态
HAL_GPIO_TogglePin(GPIOx, GPIO_Pin)//反转电平
```
![[Pasted image 20260514170940.png]]
从 io 口开始看，电压$> V_{DD}$时电压被引入电源网络吸收；电压$< V_{SS}$时，被引入0V的GND，但只能抵御瞬间电压波动。有io Level有FT标记的io口为5V容忍
- 推挽输出：使用芯片电压驱动
	- 如使用`HAL_GPIO_WritePin`函数内部对寄存器数据进行修改，使P-Mos激活，$V_{DD}$导通
- 开漏输出：使用外部电压驱动，函数寄存器控制仅用于形成闭合通路（拉高为高阻态）
- 浮空输入模式：不设置上拉/下拉
- 上拉/下拉：读取数字信号（经过肖特基触发器对模拟信号进行转换为数字信号）

# 中断
外部中断：触发来自外部的中断
- 操作
	在 CubeMX 中：
	设置 `GPIO_EXIT12` 
	`GPIO_MODE`中设置上升沿/下降沿/都触发中断
	`NVIC`:中断向量
	在`_it.c`的文件中的`EXITxx_xx_IRQHandler`内修改逻辑代码
- 理论
	![[Pasted image 20260515113124.png]]
	(高电平 = 1 ； 低电平 = 0)
	边缘检测电路经过或门，请求挂起寄存器与中断屏蔽寄存器经过与门（两者均置1）进入NVIC
	NVIC(嵌套向量中断控制器)：对照中断向量表，看`EXITxx_xx_IRQHandler`对应的xx
	为清除请求寄存器，CubeMX会自动使用`HAL_GPIO_EXIT_IRQHandler` 
	==抢占优先级决定能不能打断别人；响应优先级决定大家都在等待时谁先执行==
	eg：中断A执行过程中中断B到达，比较抢占优先级

# 串口
## 轮询模式
- 操作
	```
	TX(发射)-----RX(接收)
	RX-----TX
	GND-----GND
	```
	配置connectivity→Mode:Asynchronous
	配置好后注意波特率，通信两设备需要相同波特率
	USB转TTL连接，安装CH340驱动，安装串口助手
	使用`HAL_UART_Receive(huart, pData, Size, Timeout)`函数（Transmit同理）
- 原理
	![[Pasted image 20260515123504.png]]
	CPU不断检测发送数据寄存器是否将数据移动到移位寄存器中
	若发送数据寄存器空闲则将数据移到发送数据寄存器中
	发送移位寄存器中的数据按波特率转译成高低电平进行发送
## 串口中断模式
配置NVIC→USARTx global interrupt
使用`HAL_UART_Transmit_IT(huart, pData, Size)`
注意：在 while 前使用上述函数，并将处理逻辑移入`HAL_UART_RxCpltCallback`中，由于该函数为弱定义，可以重新定义该函数，并写入逻辑
## DMA
配置USARTx→DMA Setting→add
使用`HAL_UART_Transmit_DMA(huart, pData, Size)`
串口空闲中断——接受不定长串口数据
使用`HAL_UARTEx_ReceiveToIdle_xx(huart, pData, Size)`，该函数Ex表扩展，xx有DMA,IT和普通三种模式,Size填写一次接受的最大数组长度
类似于`HAL_UART_RxCpltCallback`函数，`HAL_UARTEx_RxEventCallback`函数也可以进行定义，其多一个入参Size
```c
//该函数的原定义
__weak void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
/* Prevent unused argument(s) compilation warning */
UNUSED(huart);
UNUSED(Size);
/* NOTE : This function should not be modified, when the callback is needed,
the HAL_UARTEx_RxEventCallback can be implemented in the user file.
*/
}
```
使用`__HAL_DMA_DISABLE_IT()`关闭DMA传输过半中断（一般情况下也可以设置很大的Size）
入参：DMA通道的指针地址；要关闭的中断

# I2C通信
```
SDA-----SDA
SCL-----SCL
GND-----GND
```
SDA允许双向通信，但不能同时双向通信，称为“半双工模式”，在SDA上，每个设备有唯一的地址
SCL是时钟线，主机会发送统一的时钟频率
阅读传感器手册写代码：传感器读取流程
事件中断：防止非阻塞函数只发送数据，未等待数据接收完成导致接受数据不对，写成状态机