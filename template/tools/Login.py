import random
import time
import json
import sys
import os
from base64 import b64decode
import requests
import configparser
from getUrl_Id import getschool_Url_Id, encrypt_sm4, decrypt_sm4, md5_encryption

conf = configparser.ConfigParser()

class Login:
    @staticmethod
    def main():
        utc = int(time.time())
        conf.read('./config.ini', encoding='utf-8')

        # 1. 确保基础配置区块存在
        if 'Login' not in conf.sections():
            conf.add_section('Login')
            conf.set('Login', 'username', '')
            conf.set('Login', 'password', '')
            with open('./config.ini', 'w', encoding='utf-8') as f: conf.write(f)

        if 'school_id' not in conf['Yun']:
            conf.set('Yun', 'school_id', '100')
            with open('./config.ini', 'w', encoding='utf-8') as f: conf.write(f)

        # 2. 静默读取配置（彻底移除所有 input()）
        username = conf.get('Login', 'username', fallback='').strip()
        password = conf.get('Login', 'password', fallback='').strip()
        if not username or not password:
            print("错误: config.ini 中 [Login] 缺少 username/password，无法登录。")
            sys.exit(1)

        iniDeviceId = conf.get('User', 'device_id', fallback='')
        iniDeviceName = conf.get('User', 'device_name', fallback='')
        iniuuid = conf.get('User', 'uuid', fallback='')
        iniSysedition = conf.get('User', 'sys_edition', fallback='')
        
        appedition = conf.get('Yun', 'app_edition', fallback='3.5.10')
        platform = conf.get('Yun', 'platform', fallback='android')
        schoolName = conf.get('Yun', 'school_name', fallback='').strip()
        
        if not schoolName:
            print("错误: 缺少 school_name，请在 config.ini [Yun] 中配置。")
            sys.exit(1)

        # 动态获取学校接口（失败则使用已配 host）
        try:
            url, scId = getschool_Url_Id(schoolName)
            if url and scId:
                conf.set('Yun', 'school_host', url)
                conf.set('Yun', 'school_id', str(scId))
                with open('./config.ini', 'w', encoding='utf-8') as f: conf.write(f)
        except Exception as e:
            print(f"警告: 动态获取学校URL失败，将使用已配置地址: {e}")

        schoolid = conf.get('Yun', 'school_id')
        schoolHost = conf.get('Yun', 'school_host')
        school_login_url = conf.get('Yun', 'school_login_url', fallback='appLogin')
        req_url = f"{schoolHost}/login/{school_login_url}"

        # 3. 设备信息处理（非交互式 fallback）
        DeviceId = iniDeviceId if iniDeviceId else str(random.randint(10**15, 10**16 - 1))
        uuid = iniuuid if iniuuid else DeviceId
        DeviceName = iniDeviceName if iniDeviceName else "Xiaomi(M2011K2C)"
        sys_edition = iniSysedition if iniSysedition else "13"

        # 保存可能自动补全的配置
        conf.set('User', 'device_id', DeviceId)
        conf.set('User', 'uuid', uuid)
        with open('./config.ini', 'w', encoding='utf-8') as f: conf.write(f)

        # 4. 加密与请求
        encryptData = json.dumps({
            "password": password,
            "schoolId": schoolid,
            "userName": username,
            "type": "1"
        })

        md5key = conf.get('Yun', 'md5key')
        sign_data = f"platform={platform}&utc={utc}&uuid={uuid}&appsecret={md5key}"
        sign = md5_encryption(sign_data)

        default_key = conf.get('Yun', 'cipherkey')
        CipherKeyEncrypted = conf.get('Yun', 'cipherkeyencrypted')
        content = encrypt_sm4(encryptData, b64decode(default_key), isBytes=False)

        headers = {
            "token": "", "isApp": "app", "deviceId": uuid, "deviceName": DeviceName,
            "version": appedition, "platform": platform, "uuid": uuid, "utc": str(utc),
            "sign": sign, "Content-Type": "application/json; charset=utf-8",
            "Accept-Encoding": "gzip", "User-Agent": "okhttp/3.12.0"
        }

        data = {"cipherKey": CipherKeyEncrypted, "content": content}

        # 增加网络超时，防止服务器无响应时永久阻塞
        try:
            response = requests.post(req_url, headers=headers, json=data, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            sys.exit(1)

        if response.status_code != 200:
            print(f"登录失败 HTTP {response.status_code}: {response.text}")
            sys.exit(1)

        # 5. 响应解密与校验
        result = response.text
        try:
            DecryptedData = response.json() if result.strip().startswith('{') else \
                            json.loads(decrypt_sm4(result, b64decode(default_key)).decode())
        except Exception as e:
            print(f"响应解析失败: {e}")
            sys.exit(1)

        if 'data' not in DecryptedData or 'token' not in DecryptedData.get('data', {}):
            print(f"登录失败，服务器返回: {DecryptedData}")
            sys.exit(1)

        token = DecryptedData['data']['token']
        print(f"登录成功 | Token: {token[:12]}... | UUID: {uuid}")
        
        # 严格返回 main.py 与 task_manager 期望的元组格式
        return token, DeviceId, DeviceName, uuid, sys_edition
