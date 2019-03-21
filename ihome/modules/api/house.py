from datetime import datetime
from flask import current_app, jsonify, request, g, session, json,make_response
from ihome import sr, db
from ihome.models import Area, House, Facility, HouseImage, Order, User
from ihome.modules.api import api_blu
from ihome.utils import constants
from ihome.utils.common import login_required
from ihome.utils.constants import AREA_INFO_REDIS_EXPIRES, QINIU_DOMIN_PREFIX, HOUSE_LIST_PAGE_CAPACITY, \
    HOME_PAGE_MAX_HOUSES, HOME_PAGE_DATA_REDIS_EXPIRES
from ihome.utils.image_storage import storage_image
from ihome.utils.response_code import RET


# 我的发布列表
@api_blu.route('/user/houses')
@login_required
def get_user_house_list():
    """
    获取用户房屋列表
    1. 获取当前登录用户id
    2. 查询数据
    :return:
    """
    # 获取登录用户的id
    user_id = g.user_id

    # 查询数据
    houses_list = []
    try:
        houses = House.query.filter(House.user_id == user_id).all()
        # user = User.query.get(user_id)
        # houses = user.houses
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询房屋数据异常")


    for house in houses:
        houses_list.append(house.to_basic_dict())


    return jsonify(errno=0, errmsg='OK', data=houses_list)


# 获取地区信息
@api_blu.route("/areas")
def get_areas():
    """
    1. 查询出所有的城区
    2. 返回
    :return:
    """
    # 获取城区信息
    try:
        area_id = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="获取城区信息错误")
    area_dict = []
    for areas in area_id if area_id else []:
        area_dict.append(areas.to_dict())
    json_area = json.dumps(area_dict)

    return '{"errno":"0", "errmsg":"OK", "data":%s}' % json_area, 200, {"Content-Type": "application/json"}




# 上传房屋图片
@api_blu.route("/houses/<int:house_id>/images", methods=['POST'])
@login_required
def upload_house_image(house_id):
    """
    1. 取到上传的图片
    2. 进行七牛云上传
    3. 将上传返回的图片地址存储
    4. 进行返回
    :return:
    """
    house_id = house_id
    images = request.files.get("house_image")

    if not all([house_id, images]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询房间数据异常")

    if house is None:
        return jsonify(errno=RET.NODATA, errmsg="房间不存在")

    images_data = images.read()

    try:
        file_name = storage_image(images_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传失败")

    house_image = HouseImage()
    house_image.house_id = house_id
    house_image.url = file_name

    try:
        db.session.add(house_image)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存图片异常")

    image_url = constants.QINIU_DOMIN_PREFIX + file_name
    print(image_url)
    return jsonify(errno=RET.OK, errmsg="OK", data={"url": image_url})


# 发布房源
@api_blu.route("/houses", methods=["POST"])
@login_required
def save_new_house():
    """
    1. 接收参数并且判空
    2. 将参数的数据保存到新创建house模型
    3. 保存house模型到数据库
    前端发送过来的json数据
    {
        "title":"",
        "price":"",
        "area_id":"1",
        "address":"",
        "room_count":"",
        "acreage":"",
        "unit":"",
        "capacity":"",
        "beds":"",
        "deposit":"",
        "min_days":"",
        "max_days":"",
        "facility":["7","8"]
    }
    :return:
    """
    user_id = g.user_id
    house_data = request.get_json()

    title = house_data.get("title")
    price = house_data.get("price")
    area_id = house_data.get("area_id")
    address = house_data.get("address")
    room_count = house_data.get("room_count")
    acreage = house_data.get("acreage")
    unit = house_data.get("unit")
    capacity = house_data.get("capacity")
    beds = house_data.get("beds")
    deposit = house_data.get("deposit")
    min_days = house_data.get("min_days")
    max_days = house_data.get("max_days")

    if not all([title, price, area_id, address, room_count, acreage, unit, capacity, beds, deposit, min_days, max_days]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 判断房屋单价和押金是否为正确参数
    try:
        price = int(float(price) * 100)
        deposit = int(float(deposit) * 100)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")


    # 查询城区id是否存在
    try:
        area = Area.query.get(area_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="城区查询异常")
    if area is None:
        return jsonify(errno=RET.NODATA, errmsg="参数有误")

    house = House()

    house.user_id = user_id
    house.title = title
    house.price = price
    house.area_id = area_id
    house.address = address
    house.room_count = room_count
    house.acreage = acreage
    house.unit = unit
    house.capacity = capacity
    house.beds = beds
    house.deposit = deposit
    house.min_days = min_days
    house.max_days = max_days

    facility_id = house_data.get("facility")

    facilities = None

    if facility_id:
        try:
            # 如果facility_id在Facility中, 才查询出来
            facilities = Facility.query.filter(Facility.id.in_(facility_id)).all()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="参数有误")

    if facilities:
        house.facilities = facilities
        try:
            db.session.add(house)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存数据异常")

    return jsonify(errno=RET.OK, errmsg="OK", data={"house_id": house.id})


# 房屋详情
@api_blu.route('/houses/<int:house_id>')
def get_house_detail(house_id):
    """
    分析：①在房屋详情页面，角色分为房东以及客户，当客户进入时对于前端页面来说需显示预定功能按钮，如是房东角色进入就不展示此功能按钮；
    ②对于角色来说，那么就需要用到user_id了；
    ③尝试从session中去获取用户id，如果存在，说明用户为登录状态，那么将用户id返回给前端，不存在返回user_id = -1

    """
    user_id = session.get("user_id", "-1")
    if not house_id:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    house_list = None  # type:House
    try:
        house_list = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="查询房屋信息失败")
    if not house_list:
        return jsonify(errno=RET.NODATA, errmsg="房屋不存在")
    # 将房屋列表转字典对象
    house_dict_list = house_list.to_full_dict()

    # 将房屋详情数据转换成json格式的数据，并存到redis数据库中
    try:
        json_houses = json.dumps(house_dict_list)
        sr.setex("house_info_%s" % house_id, constants.HOUSE_DETAIL_REDIS_EXPIRE_SECOND, json_houses)
    except Exception as e:
        current_app.logger.error(e)
    # 尝试从redis数据库中获取房屋详情信息, 出现异常则使ret为None，所以需要在进入函数后，那么需要从去数据库中获取房屋详情信息
    try:
        ret = sr.get("house_info_%s" % house_id)
    except Exception as e:
        current_app.logger.error(e)
        ret = None
    # 对ret进行判断, 存在不为None 则直接返回正确响应数据即可
    if ret:
        current_app.logger.info("house info from redis")
        return '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, ret), 200, {
            "Content-Type": "application/json"}

    resp = '{"errno":"0", "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, json_houses), 200, {
        "Content-Type": "application/json"}
    return resp


# 获取首页展示内容 /api/v1.0/houses/index
@api_blu.route('/houses/index')
def house_index():
    """
    获取首页房屋列表
    :return:
    """
    try:
        # 查询房屋订单倒序排序并显示5条
        houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="查询信息失败")
    if not houses:
        return jsonify(errno=RET.NODATA, errmsg="无相关数据")
    # 将对象列表转字典对象
    houses_list = []
    for house in houses if houses else []:
        houses_list.append(house.to_basic_dict())

    try:
        json_houses = json.dumps(houses_list)
        sr.setex("home_page_data", constants.HOME_PAGE_DATA_REDIS_EXPIRES, json_houses)
    except Exception as e:
        current_app.logger.error(e)

    return '{"errno":"0", "errmsg":"OK", "data":%s}' % json_houses, 200, {"Content-Type": "application/json"}


# 搜索房屋/获取房屋列表
@api_blu.route('/houses')
def get_house_list():
    start_date = request.args.get("sd")  # 用户入住日期
    end_date = request.args.get("ed")  # 用户离开日期
    area_id = request.args.get("aid")  # 入住区县
    sort_key = request.args.get("sk", "new")  # 排序关键字,当未选择排序条件时，默认按最新排序，这个new关键字根据前端定义走的
    page = request.args.get("p")  # 页数
    print(start_date,end_date)
    try:
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")

        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        # 当用户两者都选择情况下，需要进行判断，入住日期肯定是小于或等于离开日期的
        if start_date and end_date:
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="日期参数有误")
    if area_id:
        try:
            area = Area.query.get(area_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="区县参数有误")

    try:
        page = int(page)
    except Exception as e:
        # 如果出现异常则使page=1
        page = 1
        current_app.logger.error(e)
    # 定义过滤条件的参数列表容器以及存放冲突订单对象
    filter_params = []
    conflict_orders = None
    try:
        if start_date and end_date:
            # 查询冲突的订单所有对象
            conflict_orders = Order.query.filter(Order.begin_date <= end_date, Order.end_date >= start_date).all()
        elif start_date:
            # 用户只选择入住日期
            conflict_orders = Order.query.filter(Order.end_date >= start_date).all()
        elif end_date:
            # 用户只选择离开日期
            conflict_orders = Order.query.filter(Order.begin_date <= end_date).all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")
    if conflict_orders:
        # 从订单中获取冲突的房屋id
        conflict_house_ids = [order.house_id for order in conflict_orders]  # 使用列表生成式进行简写操作

        # 如果冲突的房屋id不为空，向查询参数中添加条件
        if conflict_house_ids:
            filter_params.append(House.id.notin_(conflict_house_ids))
    if area_id:
        filter_params.append(House.area_id == area_id)

    if sort_key == "booking":  # 入住做多
        house_query = House.query.filter(*filter_params).order_by(House.order_count.desc())
    elif sort_key == "price-inc":  # 价格低-高
        house_query = House.query.filter(*filter_params).order_by(House.price.asc())
    elif sort_key == "price-des":  # 价格高-低
        house_query = House.query.filter(*filter_params).order_by(House.price.desc())
    else:
        # 如果用户什么都没选择，则按照最新排序（数据库字段创建时间）
        house_query = House.query.filter(*filter_params).order_by(House.create_time.desc())

    try:
        page_obj = house_query.paginate(page=page, per_page=constants.HOUSE_LIST_PAGE_CAPACITY, error_out=False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")
    # 获取分页页面数据
    houses = []
    house_list = page_obj.items
    for house in house_list:
        houses.append(house.to_basic_dict())
    # 获取总页数，并返回正确响应数据
    total_page = page_obj.pages
    return jsonify(errno=RET.OK, errmsg="OK", data={"houses": houses, "total_page": total_page, "current_page": page})