from datetime import datetime
from ihome import db, sr
from ihome.models import House, Order
from ihome.utils.common import login_required
from ihome.utils.response_code import RET
from . import api_blu
from flask import request, g, jsonify, current_app, session



# 预订房间
@api_blu.route('/orders', methods=['POST'])
@login_required
def add_order():
    """
    下单
    1. 获取参数
    2. 校验参数
    3. 查询指定房屋是否存在
    4. 判断当前房屋的房主是否是登录用户
    5. 查询当前预订时间是否存在冲突
    6. 生成订单模型，进行下单
    7. 返回下单结果
    :return:
    """
    param_dict = request.json
    start_date_str = param_dict.get('start_date')
    end_date_str = param_dict.get('end_date')
    house_id = param_dict.get('house_id')
    user_id = g.user_id

    # 校验参数
    if not all([start_date_str, end_date_str, house_id]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不足')

    # 查询房屋是否存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询房屋数据异常")
    if not house:
        return jsonify(errno=RET.NODATA, errmsg='房屋不存在')

    # 判断当前房屋的房主是否是登录用户
    if user_id == house.user_id:
        return jsonify(errno=RET.DATAERR, errmsg='用户为屋主,不能预定')

    # 转换时间格式,查询当前预订时间是否存在冲突
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    try:
        order_count = Order.query.filter(Order.house_id == house_id, Order.begin_date < end_date, Order.end_date > start_date).count()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询订单数据异常")
    if order_count > 0:
        return jsonify(errno=RET.DATAERR, errmsg='该时间段已有订单')

    # 计算入住天数以及总价格
    days = (end_date-start_date).days + 1
    amount = house.price * days

    # 生成订单模型，进行下单
    order = Order()
    order.user_id = user_id
    order.house_id = house_id
    order.begin_date = start_date
    order.end_date = end_date
    order.house_price = house.price
    order.days = days
    order.amount = amount
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存订单数据异常")
    # 返回数据
    return jsonify(errno=0, errmsg='OK', data={'order_id': order.id})


# 获取我的订单
@api_blu.route('/orders')
@login_required
def get_orders():
    """
    1. 去订单的表中查询当前登录用户下的订单
    2. 返回数据
    :return:
    """
    # 1获取参数
    role = request.args.get('role', '')
    user_id = g.user_id
    try:
        # 1.1登录用户是屋主
        if role == 'landlord':
            houses = House.query.filter(House.user_id == user_id)
            houses_ids = [house.id for house in houses]
            # 在Order表中查询预定了自己房子的订单,并按照创建订单的时间的倒序排序，也就是在此页面显示最新的订单信息
            orders = Order.query.filter(Order.house_id.in_(houses_ids)).order_by(Order.create_time.desc()).all()

        # 1.2登录用户是租客
        else:
            # 查询租客的订单列表
            orders = Order.query.filter(Order.user_id == user_id).order_by(Order.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询用户订单数据异常")

    # 组织用户订单数据并返回
    orders_dict_list = []
    if orders:
        for order in orders:
            orders_dict_list.append(order.to_dict())
    return jsonify(errno=0, errmsg='OK', data={"orders":orders_dict_list})


# 接受/拒绝订单
@api_blu.route('/orders', methods=["PUT"])
@login_required
def change_order_status():
    """
    1. 接受参数：order_id
    2. 通过order_id找到指定的订单，(条件：status="待接单")
    3. 修改订单状态
    4. 保存到数据库
    5. 返回
    :return:
    """
    # 1.接受参数：order_id
    # order_id = order_id
    param_dict = request.get_json()
    action = param_dict.get("action")
    reason = param_dict.get("reason")
    order_id = param_dict.get("order_id")

    user_id = g.user_id

    if not all([order_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if action not in ["accept", "reject"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 2.通过order_id找到指定的订单，(条件：status="待接单")
    try:
        order = Order.query.filter(Order.id == order_id, Order.status == "WAIT_ACCEPT").first()
        house_id = order.house_id

        # 根据订单房屋id查询房屋对象
        house = House.query.get(house_id)



    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询订单对象异常")

    # 如果order对象不存在或者订单中的房屋id不等于用户id 则说明房东在修改不属于自己房屋订单
    if not order or house.user_id != user_id:
        return jsonify(errno=RET.REQERR, errmsg="操作无效")

    # 3.修改订单状态
    if action == "accept":
        order.status = "WAIT_COMMENT"
    else:
        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg="请输入拒绝原因")

        order.status = "REJECTED"
        order.comment = reason
    # 4.保存到数据库
    try:
        db.session.add(order)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存订单状态异常")
    # 5.返回
    return jsonify(errno=0, errmsg="OK")




# 评论订单
@api_blu.route('/orders/comment', methods=["PUT"])
@login_required
def order_comment():
    """
    订单评价
    1. 获取参数
    2. 校验参数
    3. 修改模型
    :return:
    """

    # 1.获取参数
    param_dict = request.get_json()
    comment = param_dict.get("comment")
    order_id = param_dict.get("order_id")
    user_id = g.user_id


    # 2.校验参数
    if not comment:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 查询订单,确保用户只能评价自己的订单并且订单处于待评价的状态
    try:
        order = Order.query.filter(Order.id == order_id, Order.user_id == user_id, Order.status == "WAIT_COMMENT").first()
        house_id = order.house_id
        # 根据订单房屋id查询房屋对象
        house = House.query.get(house_id)

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询订单异常")

    if not order:
        return jsonify(errno=RET.NODATA, errmsg="订单不存在")

    # 3.修改模型

    # 保存评价信息
    order.comment = comment
    # 将订单的状态设置为已完成
    order.status = "COMPLETE"
    # 将房屋完成订单数加1
    house.order_count += 1


    # 4.保存到数据库
    try:
        db.session.add(order)
        db.session.add(house)
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存评价异常")

    # 为了在房屋详情中显示最新的评价信息，所以需要删除redis中该订单对应的房屋的信息
    try:
        sr.delete("house_info_%s" % order.house_id)

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="删除redis中该订单对应的房屋的信息异常")

    # 5.返回
    return jsonify(errno=RET.OK, errmsg="OK")


