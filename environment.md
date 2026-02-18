# Python V3.12
# All .py scripts share the same virtual environment

## 创建虚拟环境（首次或重建时）

在项目根目录执行：

```powershell
python -m venv .venv
```

若因权限/网络导致 pip 未安装，可先创建无 pip 的 venv 再手动安装 pip：

```powershell
python -m venv .venv --without-pip
.venv\Scripts\python -m ensurepip --upgrade
```

## 激活虚拟环境

**PowerShell：**
```powershell
.\.venv\Scripts\Activate.ps1
```

**CMD：**
```cmd
.venv\Scripts\activate.bat
```

激活后安装依赖并运行脚本：
```powershell
pip install -r requirements.txt
python license-prep.py
```