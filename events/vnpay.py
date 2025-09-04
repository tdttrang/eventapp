import hmac
import hashlib
import urllib.parse


class vnpay:
    def __init__(self):
        # requestData: dữ liệu gửi sang VNPAY
        self.requestData = {}
        # responseData: dữ liệu nhận từ VNPAY (return, ipn)
        self.responseData = {}

    def get_payment_url(self, vnpay_payment_url, secret_key):
        """
        Build URL thanh toán để redirect sang VNPAY
        """
        # ✅ Sắp xếp theo alphabet
        inputData = sorted(self.requestData.items())

        # Chuỗi hashData để ký (không encode value)
        hashData = "&".join([f"{k}={v}" for k, v in inputData])

        # Chuỗi queryString để build URL (encode value theo chuẩn VNPAY: space -> +)
        queryString = "&".join(
            [f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in inputData]
        )

        # ✅ Tính chữ ký HMAC SHA512
        secure_hash = hmac.new(
            secret_key.encode("utf-8"),
            hashData.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()

        # # Append secure hash
        # full_url = (
        #     f"{vnpay_payment_url}?{queryString}"
        #     f"&vnp_SecureHashType=HMACSHA512&vnp_SecureHash={secure_hash}"
        # )

        # Không gửi vnp_SecureHashType (một số sandbox/endpoint từ chối sớm nếu có)
        full_url = f"{vnpay_payment_url}?{queryString}&vnp_SecureHash={secure_hash}"

        # Log debug
        print(">>> [VNPAY get_payment_url] hashData:", hashData)
        print(">>> [VNPAY get_payment_url] queryString:", queryString)
        print(">>> [VNPAY get_payment_url] secure_hash:", secure_hash)

        return full_url

    def validate_response(self, secret_key):
        """
        Validate chữ ký khi nhận dữ liệu từ VNPAY (return / ipn)
        """
        vnp_SecureHash = self.responseData.get("vnp_SecureHash", "")
        vnp_SecureHashType = self.responseData.get("vnp_SecureHashType", "")

        # Copy data rồi loại bỏ SecureHash và SecureHashType
        inputData = self.responseData.copy()
        inputData.pop("vnp_SecureHash", None)
        inputData.pop("vnp_SecureHashType", None)

        # Sắp xếp key để hash
        inputData = sorted(inputData.items())
        hashData = "&".join([f"{k}={v}" for k, v in inputData])

        # Tính hash lại
        secure_hash = hmac.new(
            secret_key.encode("utf-8"),
            hashData.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()

        # Log debug
        print(">>> [VNPAY validate_response] hashData (local):", hashData)
        print(">>> [VNPAY validate_response] calculated hash:", secure_hash)
        print(">>> [VNPAY validate_response] vnp_SecureHash (from VNPAY):", vnp_SecureHash)
        print(">>> [VNPAY validate_response] vnp_SecureHashType:", vnp_SecureHashType)

        # So sánh không phân biệt hoa thường
        return secure_hash.upper() == vnp_SecureHash.upper()
