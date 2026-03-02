# Python V3.12
# All .py scripts share the same virtual environment

## for MacOS 
python3 --version && which python3
python3 -m venv .venv 
source .venv/bin/activate 
pip install -r requirements.txt 


## for Windows 

```powershell
python -m venv .venv
```
若因权限/网络导致 pip 未安装，可先创建无 pip 的 venv 再手动安装 pip：
```powershell
python -m venv .venv --without-pip
.venv\Scripts\python -m ensurepip --upgrade
```

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