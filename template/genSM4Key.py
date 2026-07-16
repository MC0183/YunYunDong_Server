# Description: 生成SM4密钥，并转换为Base64字符串
from gmssl import sm4, func
import base64

# 生成32位HEX字符串（对应16字节密钥）
key_hex = func.random_hex(32)
key_bytes = bytes.fromhex(key_hex)  # 转换为字节类型

# 转换为Base64字符串
key_base64 = base64.b64encode(key_bytes).decode('utf-8')

print("SM4 Key (Base64):", key_base64)
