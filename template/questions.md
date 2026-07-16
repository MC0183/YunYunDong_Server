#### 这里提供11个常见问题

1. 报错 'data' 然后NoneType xxx
- 检查你的config有没有读到，有没有正确填写

2. {"msg":"请求访问：/run/getHomeRunInfo，认证失败，无法访问系统资源","code":401}
- 检查你的token和school_host

3. No module named xxx
- `pip -r requirements.txt`
- 如果还有问题，把缺的库写到`requirements.txt`里面，然后PR

4. hosts处连接超时怎么办
- 检查网络问题，考虑校园网换热点等
- 如果你开着VPN或者抓包，尝试关闭它们

5. 代理报错
- 3.4.7以后不保证这个功能可用，没有维护

6. 登录问题
- 首先不推荐登录，尽量保持token一致
- 其次3.4.7以后不保证登录可以正常使用，没有维护

7. no such file or directory
- cd到项目目录执行Python命令

8. invalid cipher text
- 3.4.7私钥失效了，别解密了
- 如果是旧版本的，先检查你base64编码有没有错，有的话就是填写问题
- 还没有错的话检查gzip有没有使用

9. 一直回跑的问题
- 首先这个功能很久没维护了
- 注意更改config.ini里面的起始点，别从我们学校操场飞到你们学校了

10. {"msg":"服务异常，请稍后再试","code":500}
- 检查你密钥的配置，cipherKey和cipherkeyencrypted都要填
- 检查你版本信息，别和最新版本差太多

11. keyError: 'data'
- 账户密码和学校不匹配，检查下school_host和school_id
- `python getUrl_id.py` 来获得你学校的host和id