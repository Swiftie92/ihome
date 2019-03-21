function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}

function generateUUID() {
    var d = new Date().getTime();
    if(window.performance && typeof window.performance.now === "function"){
        d += performance.now(); //use high-precision timer if available
    }
    var uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = (d + Math.random()*16)%16 | 0;
        d = Math.floor(d/16);
        return (c=='x' ? r : (r&0x3|0x8)).toString(16);
    });
    return uuid;
}


function sendSMScode() {
    // 校验参数，保证输入框有数据填写
    $(".phonecode-a").removeAttr("onclick");
    var mobile = $("#mobile").val();
    if (!mobile) {
        $("#mobile-err span").html("请填写正确的手机号！");
        $("#mobile-err").show();
        $(".phonecode-a").attr("onclick", "sendSMScode();");
        return;
    } 


    var params = {
        "mobile": mobile,
        "phonecode":phonecode

    }

    //  通过ajax方式向后端接口发送请求，让后端发送短信验证码
    $.ajax({
        url: "/api/v1.0/login_send_sms",
        type: "post",
        data: JSON.stringify(params),
        headers: {
            "X-CSRFToken": getCookie("csrf_token")  //获取当前浏览器中cookie中的csrf_token
        },
        contentType: "application/json",
        success: function (resp) {
            if (resp.errno == "0") {
                // 代表发送成功
                var num = 60
                var t = setInterval(function () {
                    if (num == 1) {
                        // 倒计时结束,将当前倒计时给清除掉
                        clearInterval(t)
                        $(".phonecode-a").attr("onclick", "sendSMScode();");
                        $(".phonecode-a").html("获取验证码")
                    }else {
                        // 正在倒计时
                        num -= 1
                        $(".phonecode-a").html(num + "秒")
                    }
                }, 1000, 60)
            }else {
                // 将发送短信的按钮置为可以点击
                $(".phonecode-a").attr("onclick", "sendSMScode();");
                // 发送短信验证码失败
                alert(resp.errmsg)
            }
        }
    })
}

$(document).ready(function() {
    $("#phonecode").focus(function () {
        $("#phone-code-err").hide();
    });
    });
    // 注册的提交(判断参数是否为空)
    
    $(".form-login-sms").submit(function (e) {
        e.preventDefault()

        // 取到用户输入的内容
        var mobile = $("#mobile").val()
        var phonecode = $("#phonecode").val()

        if (!mobile) {
            $("#mobile-err span").html("请填写正确的手机号！");
            $("#mobile-err").show();
            return;
        }
        if (!phonecode) {
            $("#phone-code-err span").html("请填写短信验证码！");
            $("#phone-code-err").show();
            return;
        }

        // var params = {
        //     "mobile": mobile,
        //     "phonecode": phonecode,
        //     "password": password,
        // }

        // 方式2：拼接参数
        var params = {}
        $(this).serializeArray().map(function (x) {
            params[x.name] = x.value
        })

        $.ajax({
            url:"/api/v1.0/login_sms",
            type: "post",
            headers: {
                "X-CSRFToken": getCookie("csrf_token")
            },
            data: JSON.stringify(params),
            contentType: "application/json",
            success: function (resp) {
                if (resp.errno == "0"){
                    // 直接回到首页
                    location.href = "/set_new_password.html"
                }else {
                    $("#password2-err span").html(resp.errmsg)
                    $("#password2-err").show()
                }
            }
        })
    })
