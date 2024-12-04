# Computer Use - OOTB

## 🌟 概述
开箱即用 Claude Computer Use。

**无需 Docker**，理论上支持**任何平台**，目前在 **Windows** 上进行了测试。此项目基于 Gradio Web 框架。🎨

## 更新
- 10-25: 现在你可以通过移动设备 📱 **远程控制** 你的电脑 💻 ——**无需安装移动应用**！快来试试吧 🎉。

## 演示视频

[![观看视频](https://img.youtube.com/vi/VH9bEUkdIAY/maxresdefault.jpg)](https://youtu.be/VH9bEUkdIAY)

## 🚀 入门指南

### 0. 准备工作
- 通过这个 [链接](https://www.anaconda.com/download?utm_source=anacondadocs&utm_medium=documentation&utm_campaign=download&utm_content=topnavalldocs) 安装 Miniconda。（**Python 版本: >= 3.11**）。

### 1. 克隆代码仓库 📂
打开 Conda 终端。（安装 Miniconda 后，它会出现在“开始”菜单中。）在 **Conda 终端** 中运行以下命令。
```bash
git clone https://github.com/showlab/computer_use_ootb.git
cd computer_use_ootb
```

### 2. 安装依赖项 🔧
```bash
pip install -r dev-requirements.txt
```

### 3. 启动界面 ▶️
```bash
python app.py
```
如果成功启动界面，终端中会显示两个 URL：
```bash
* 本地 URL:  http://127.0.0.1:7860
* 公共 URL: https://xxxxxxxxxxxxxxxx.gradio.live （请不要将此链接分享给他人，否则他们将能够控制你的计算机。）
```

### 4. 使用任何设备控制你的计算机（只需可以访问互联网）
- **要被控制的计算机**：已安装软件的计算机。
- **发送指令的设备**：打开网站的设备。

在要控制的计算机上打开 http://localhost:7860/，或在手机浏览器中访问 https://xxxxxxxxxxxxxxxxx.gradio.live 进行远程控制。

输入 Anthropic API 密钥（可以通过这个 [网站](https://console.anthropic.com/settings/keys) 获取），然后给 AI 下达命令来执行你的任务。

移动端界面

<img src="./assets/gradio_mobile.jpg" alt="gradio_interface" width="30%">

桌面端界面
![gradio_interface](./assets/gradio_interface.png)

## 🖥️ 支持的系统
- **Windows** ✅

## ⚠️ 风险
- **模型可能执行危险操作**：模型的表现仍然有限，可能会生成意外或潜在有害的输出。建议持续监控 AI 的操作。 
- **成本控制挑战**：每个任务可能花费几美元。未来我们将对此进行优化。💸

## 📅 路线图

- [ ] **界面设计**
  - [x] **支持 Gradio** ✨
  - [ ] **更简单的安装**
  - [ ] **更多功能**... 🚀
- [ ] **平台支持**
  - [x] **Windows**
  - [x] **移动端**（发送命令）
  - [ ] **Mac**
  - [ ] **移动端**（被控制）
- [ ] **支持更多多模态大语言模型（MLLMs）**
  - [x] **Claude 3.5 Sonnet** 🎵
  - [ ] **GPT-4o**
  - [ ] **Qwen2-VL**
  - [ ] ...
- [ ] **改进提示策略**
  - [ ] 优化提示语以降低成本。💡

