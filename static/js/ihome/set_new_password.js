function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}

$(document).ready(function() {
    $("#password").focus(function(){
        $("#password-err").hide();
    });
    $("#password2").focus(function(){
        $("#password2-err").hide();
    });
    //  添加登录表单提交操作
    $(".form-set_new_password").submit(function(e){
        e.preventDefault();
        password = $("#password").val();
        password2 = $("#password2").val();
        if (!password) {
            $("#password-err span").html("请填写新密码!");
            $("#password-err").show();
            return;
        }
        if (!password2) {
            $("#password2-err span").html("请确认新密码!");
            $("#password2-err").show();
            return;
        }

        var params = {
            "password": password,
            "password2": password2,
        }

        $.ajax({
            url:"/api/v1.0/set_new_password",
            method: "post",
            headers: {
                "X-CSRFToken": getCookie("csrf_token")
            },
            data: JSON.stringify(params),
            contentType: "application/json",
            success: function (resp) {
                if (resp.errno == "0") {
                    location.href = "/login.html"
                }else {
                    $("#password-err span").html(resp.errmsg)
                    $("#password-err").show()
                }
            }
        })
    });
})


