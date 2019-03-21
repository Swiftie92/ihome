from flask import request, current_app, jsonify, session, g

from ihome import db
from ihome.models import User
from ihome.modules.api import api_blu
from ihome.utils.common import login_required
from ihome.utils.constants import QINIU_DOMIN_PREFIX
from ihome.utils.image_storage import storage_image
from ihome.utils.response_code import RET


# 获取用户信息
@api_blu.route('/user')
@login_required
def get_user_info():
    """
    获取用户信息
    1. 获取到当前登录的用户模型
    2. 返回模型中指定内容
    :return:
    """
    # 获取用户信息
    user_id = g.user_id

    # 根据用户id查询用户对象
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    name = user.name
    mobile = user.mobile
    avatar_url = user.avatar_url
    full_url = QINIU_DOMIN_PREFIX + avatar_url

    return jsonify(errno=RET.OK, errmsg='获取用户信息成功', data={"name": name, "mobile":mobile, "avatar_url": full_url})


# 修改用户名
@api_blu.route('/user/name', methods=["POST"])
@login_required
def set_user_name():
    """
    0. 判断用户是否登录
    1. 获取到传入参数
    2. 将用户名信息更新到当前用户的模型中
    3. 返回结果
    :return:
    """

    # 0.判断用户是否登录
    user_id = g.user_id

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    # 1.获取到传入参数
    user_name = request.json.get('name')

    # 1.1非空判断
    if not user_name:
        return jsonify(errno=RET.PARAMERR, errmsg='请输入新的用户名')

    if user_name == user.name:
        return jsonify(errno=RET.DATAEXIST, errmsg='用户名已经存在')

    # 2.将用户名信息更新到当前用户的模型中
    user.name = user_name

    # 修改session数据, 保存到数据库
    session['name'] = user.name

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='用户名保存数据库异常')
    # 3.返回结果
    return jsonify(errno=RET.OK, errmsg='用户名修改成功')



# 上传个人头像
@api_blu.route('/user/avatar', methods=['POST'])
@login_required
def set_user_avatar():
    """
    0. 判断用户是否登录
    1. 获取到上传的文件
    2. 再将文件上传到七牛云
    3. 将头像信息更新到当前用户的模型中
    4. 返回上传的结果<avatar_url>
    :return:
    """
    # 0.判断用户是否登录
    user_id = g.user_id

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    # 1.获取到上传的文件
    avatar = request.files.get('avatar')

    # 1.1 参数判断
    if not avatar:
        return jsonify(errno=RET.PARAMERR, errmsg='图片数据为空')

    # 2.再将文件上传到七牛云
    try:
        avatar_name = storage_image(avatar.read())
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='图片上传到七牛云异常')

    # 3.将头像信息更新到当前用户的模型中
    if avatar_name:
        user.avatar_url = avatar_name

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='头像保存数据库异常')

    # 完整头像地址返回
    full_url = QINIU_DOMIN_PREFIX + avatar_name

    # avatar_url = full_url

    # 4.返回上传的结果 < avatar_url >
    return jsonify(errno=RET.OK, errmsg='上传个人头像成功', data={"avatar_url": full_url})


# 获取用户实名信息
@api_blu.route('/user/auth')
@login_required
def get_user_auth():
    """
    1. 取到当前登录用户id
    2. 通过id查找到当前用户
    3. 获取当前用户的认证信息
    4. 返回信息
    :return:
    """
    # 1.取到当前登录用户id

    user_id = g.user_id

    # 2.通过id查找到当前用户

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    # 3.获取当前用户的认证信息
    # real_name = request.args.get('real_name')
    # id_card = request.args.get('id_card')

    real_name = user.real_name
    id_card = user.id_card

    # # 3.1 非空判断
    # if not all([real_name, id_card]):
    #     return jsonify(errno=RET.PARAMERR, errmsg='参数不足')
    #
    # # 3.2 校对真实姓名
    # if real_name != user.real_name:
    #     return jsonify(errno=RET.DATAERR, errmsg='用户真实姓名错误')
    #
    # # 3.3 校对身份证号码
    # if id_card != user.id_card:
    #     return jsonify(errno=RET.DATAERR, errmsg='身份证号码错误')

    # 4.返回信息
    return jsonify(errno=RET.OK, errmsg='用户实名认证成功', data={"real_name": real_name, "id_card": id_card})



# 设置用户实名信息
@api_blu.route('/user/auth', methods=["POST"])
@login_required
def set_user_auth():
    """
    1. 取到当前登录用户id
    2. 取到传过来的认证的信息
    3. 通过id查找到当前用户
    4. 更新用户的认证信息
    5. 保存到数据库
    6. 返回结果
    :return:
    """
    user_id = g.user_id
    real_name = request.json.get("real_name")
    id_card = request.json.get("id_card")
    if not user_id:
        return jsonify(errno=RET.USERERR, errmsg="用户未登录")
    if not all([real_name, id_card]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")


    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='查询用户信息异常')

    user.real_name = real_name
    user.id_card = id_card

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="认证数据保存异常")
    return jsonify(errno=RET.OK, errmsg="ok")
