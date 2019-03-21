# 七牛上传文件的工具类
access_key = "lOxunRhNjvKssGnBtQsrVj0H_NJLCLhi4WE45dKd"

secret_key= "MhFU5UmXgGvJQ2k_Y-dliSxbiPD5bdvuJhSheiCC"
bucket_name = "flask24"  # 存储空间名称



def storage_image(data):
    """进行文件上传的工具类"""
    """
       文件上传
       :param data: 上传的文件内容
       :return: 生成的文件名
       """
    import qiniu

    q = qiniu.Auth(access_key, secret_key)
    key = None  # 文件名, 如果不设置, 会生成随机文件名
    token = q.upload_token(bucket_name)
    # 上传文件
    ret, info = qiniu.put_data(token, key, data)
    if ret is not None:
        # 返回文件名
        return ret.get("key")  # 获取生成的随机文件名

    else:
        raise BaseException(info)
    print(ret.get("key"))


if __name__ == '__main__':
    file_name = input("请输入文件名：")
    with open(file_name, "rb") as f:
        storage_image(f.read())

