# 实现图片验证码和短信验证码的逻辑
from datetime import datetime
import re, random

from alembic.autogenerate import render
from flask import request, abort, current_app, jsonify, make_response, json, session, g

from ihome import sr, db
from ihome.libs.captcha.pic_captcha import captcha
from ihome.libs.yuntongxun.sms import CCP
from ihome.models import User
from ihome.modules.api import api_blu
from ihome.utils import constants
from ihome.utils.common import login_required
from ihome.utils.response_code import RET


# 获取图片验证码 注册模块
@api_blu.route("/imagecode")
def get_image_code():
    # 1.1 code_id: UUID唯一编码
    code_id = request.args.get('cur')
    # 2.1 code_id非空判断
    if not code_id:
        return jsonify(errno=RET.PARAMERR, errmsg="image code err")
    # 2. 生成图片验证码
    image_name, sea_image_name, image_data = captcha.generate_captcha()
    # 3. 保存编号和其对应的图片验证码内容到redis
    sr.setex("Iamge_Code_%s" % code_id, constants.IMAGE_CODE_REDIS_EXPIRES, sea_image_name)
    # 4. 返回验证码图片

    response = make_response(image_data)
    response.headers["Content-Type"] = "image/png"

    return response


# 获取短信验证码
@api_blu.route('/smscode', methods=["POST"])
def send_sms():
    # 1. 接收参数并判断是否有值
    receiver = request.json
    mobile = receiver.get('mobile')
    image_code = receiver.get('image_code')
    image_code_id = receiver.get('image_code_id')

    if not all([mobile,image_code,image_code_id]):
        current_app.logger.error("参数不足")
        # 错误信息
        err_dict = {"errno": RET.PARAMERR, "errmsg": "参数不足"}
        return jsonify(err_dict)
    # 2. 校验手机号是正确
    if not re.match(r"1[2345678][0-9]{9}",mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")
    # 3. 通过传入的图片编码去redis中查询真实的图片验证码内容
    try:
        real_image_code = sr.get("Iamge_Code_%s" % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="查询失败")
    #
    if not real_image_code:
        return jsonify(errno=RET.PARAMERR, errmsg="图片失效")
    # 4. 进行验证码内容的比对
    if image_code.lower() != real_image_code.lower():
        return jsonify(errno=RET.PARAMERR, errmsg="图片错误")

    # 5. 生成发送短信的内容并发送短信
        # TODO: 判断手机号码是否已经注册 【提高用户体验】
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户数据异常")

    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg="手机号码已经注册")
    real_sms_code = random.randint(0, 999999)
    # 6位的密码
    real_sms_code = "%06d" % real_sms_code
    # 发送短信验证码
    try:
        result = CCP().send_template_sms(mobile, {real_sms_code, 5}, 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")
    # 发送短信验证码失败
    if result == -1:
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")
    # 6. redis中保存短信验证码内容
    sr.setex("SMS_CODE_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, real_sms_code)
    # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送短信验证码成功")


# 用户注册
@api_blu.route("/user", methods=["POST"])
def register():
    # 1. 获取参数和判断是否有值
    Post_register = request.json
    mobile = Post_register.get('mobile')
    ses_code = Post_register.get('phonecode')
    password = Post_register.get('password')
    if not all([mobile,ses_code,password]):
        current_app.logger.error("参数不足")
        return jsonify(errno=RET.PARAMERR,errsmg="参数不足")
    # 判断手机号码
    if not re.match(r"1[2345678][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")
    # 2. 从redis中获取指定手机号对应的短信验证码的
    try:
        real_sms_code = sr.get("SMS_CODE_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询redis中短信验证码异常")

    # 3. 校验验证码
    if ses_code != real_sms_code:
        #  3.3 不相等：短信验证码填写错误
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码填写错误")

    # 4. 初始化 user 模型，并设置数据并添加到数据库
    user = User()
    user.name = mobile
    user.mobile = mobile
    user.password = password
    # 5. 保存当前用户的状态
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="保存对象异常")
    # 6. 返回注册的结果
    return jsonify(errno=RET.OK, errmsg="注册成功")


# 用户登录
@api_blu.route("/session", methods=["POST"])
def login():
    """
    1. 获取参数和判断是否有值
    2. 从数据库查询出指定的用户
    3. 校验密码
    4. 保存用户登录状态
    5. 返回结果
    :return:
    """
    #1:获取参数
    param_dict = request.json
    mobile = param_dict.get("mobile")
    password = param_dict.get("password")
    #2:判断参数检验
    if not all([mobile,password]):
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")
    #3:判断手机号码格式
    if not re.match(r"1[35789][0-9]{9}",mobile):
        return jsonify(errno=RET.PARAMERR,errmsg="参数错误")
    #4:查询用户是否存在
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        return jsonify(errni=RET.USERERR,errmsg="用户不存在")
    if not user:
        return jsonify(errno=RET.USERERR,errmsg="用户未注册，请注册")
    #5:判断密码是否正确
    if user.check_passowrd(password) is False:
        return jsonify(errno=RET.PWDERR,errmsg="密码错误")
    # print(user)
    # #7:将修改操作提交到数据库
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(errno=RET.DBERR,errmsg="提交数据错误")
    # 8:使用session记录用户信息
    session["user_id"] = user.id
    session["mobile"] = user.mobile
    session["name"] = user.name
    # #9:返回数据
    return jsonify(errno=RET.OK ,errmsg="ok")


# 获取登录状态
@api_blu.route('/session')
def check_login():
    """
    检测用户是否登录，如果登录，则返回用户的名和用户id
    :return:
    """
    name = session.get("name")
    user_id = session.get("user_id")
    # name不为空，则返回ok，并将name以字典形式传给前端，为空则返回对应错误信息
    if name is not None:
        return jsonify(errno=RET.OK, errmsg="true", data={"name": name,"user_id":user_id})
    else:
        return jsonify(errno=RET.SESSIONERR, errmsg="false")


# 退出登录
@api_blu.route("/session", methods=["DELETE"])
def logout():
    """
    1. 清除session中的对应登录之后保存的信息
    :return:
    """
    session.pop("user_id","")
    session.pop("mobile","")
    session.pop("name","")

    return jsonify(errno=RET.OK,errmsg="退出登录成功")


# 忘记密码转登录页面发送短信验证码
@api_blu.route('/login_send_sms', methods=['POST'])
def login_send_sms():
    # 1. 接收参数并判断是否有值
    mobile = request.json.get('mobile')

    if not mobile:
        current_app.logger.error('参数不足')
        return jsonify(errno=RET.PARAMERR, errmsg='请输入手机号码')
    # 2. 校验手机号是正确
    if not re.match(r"1[2345678][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 3. 生成发送短信的内容并发送短信
    # TODO: 判断手机号码是否已经注册 【提高用户体验】
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户数据异常")

    if not user:
        # 当前手机号码未注册
        return jsonify(errno=RET.USERERR, errmsg="当前手机号码未注册")

        # 3.4.1 生成6位的随机短信
    real_sms_code = random.randint(0, 999999)

    # 6位，前面补零
    real_sms_code = "%06d" % real_sms_code
    print(real_sms_code)

    # 4.发送短信验证码成功
    try:
        result = CCP().send_template_sms(mobile, {real_sms_code, 5}, 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")

    # 发送短信验证码失败：告知前端
    if result == -1:
        return jsonify(errno=RET.THIRDERR, errmsg="云通信发送短信验证码异常")

    # 6. redis中保存短信验证码内容
    sr.setex("SMS_CODE_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, real_sms_code)

    # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送短信验证码成功")


# 短信验证码登录页面
@api_blu.route('/login_sms', methods=['POST'])
def login_sms():
    # 1. 获取参数和判断是否有值

    mobile = request.json.get("mobile")
    phonecode = request.json.get("phonecode")

    if not all([mobile, phonecode]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 2. 校验手机号是正确
    if not re.match(r"1[2345678][0-9]{9}", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号码格式错误")

    # 3. 从数据库查询出指定的用户
    try:
        user = User.query.filter(User.mobile == mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户对象异常")

    if not user:
        return jsonify(errno=RET.USERERR, errmsg="当前手机号码未注册")

    try:
        real_sms_code = sr.get("SMS_CODE_%s" % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询redis中短信验证码异常")

    # 4. 校验验证码
    if phonecode != real_sms_code:
        #  3.3 不相等：短信验证码填写错误
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码填写错误")

    # 5. 保存用户登录状态

    session["user_id"] = user.id
    session["mobile"] = user.mobile

    # 记录用户最后一次登录时间
    user.last_login = datetime.now()

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg='数据库保存用户信息异常')

    # 5. 登录成功
    return jsonify(errno=RET.OK, errmsg="OK")


# 设置新密码
@api_blu.route('/set_new_password', methods=['POST'])
@login_required
def set_new_password():
    # 1. 获取到传入参数
    data_dict = request.json
    old_password = data_dict.get("password")
    new_password = data_dict.get("password2")

    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    if old_password != new_password:
        return jsonify(errno=RET.DATAERR, errmsg='密码不相同')

    # 2. 获取当前登录用户的信息
    user_id = g.user_id

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='数据库异常')

    # if user.password == new_password:
    #     return jsonify(errno=RET.DATAEXIST, errmsg='密码不能与原本密码相同')

    # 保存新密码
    user.password = new_password

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    return jsonify(errno=RET.OK, errmsg="保存成功")


