import hashlib
import hmac
import urllib.parse

class vnpay:
    def __init__(self):
        # requestData dùng để build URL gửi đi VNPAY
        self.requestData = {}
        # responseData dùng để lưu dữ liệu callback / IPN từ VNPAY
        self.responseData = {}

    def get_payment_url(self, vnpay_payment_url, secret_key):
        # Sắp xếp tham số theo key
        inputData = sorted(self.requestData.items())
        hashData = ""
        queryString = ""

        # Ghép chuỗi query và hashData
        for idx, (key, val) in enumerate(inputData):
            if idx == 0:
                hashData = f"{key}={val}"
                queryString = f"{key}={urllib.parse.quote(str(val), safe='')}"
            else:
                hashData += f"&{key}={val}"
                queryString += f"&{key}={urllib.parse.quote(str(val), safe='')}"

        # Sinh SecureHash bằng HMAC SHA512
        secure_hash = self.__hmacsha512(secret_key, hashData)

        # Log để debug
        print(">>> [VNPAY get_payment_url] hashData:", hashData)
        print(">>> [VNPAY get_payment_url] secure_hash:", secure_hash)

        # Trả về URL hoàn chỉnh
        return f"{vnpay_payment_url}?{queryString}&vnp_SecureHash={secure_hash}"

    def validate_response(self, secret_key):
        # Lấy secure hash từ response
        vnp_SecureHash = self.responseData.get("vnp_SecureHash", "")

        # Copy dữ liệu để không làm thay đổi gốc
        data = self.responseData.copy()

        # Xóa hash params để tính lại
        data.pop("vnp_SecureHash", None)
        data.pop("vnp_SecureHashType", None)

        # Sắp xếp tham số theo key
        inputData = sorted(data.items())
        hashData = ""

        for idx, (key, val) in enumerate(inputData):
            if idx == 0:
                hashData = f"{key}={val}"
            else:
                hashData += f"&{key}={val}"

        # Tính lại hash
        secure_hash = self.__hmacsha512(secret_key, hashData)

        # Log để debug
        print(">>> [VNPAY validate_response] hashData:", hashData)
        print(">>> [VNPAY validate_response] secure_hash:", secure_hash)
        print(">>> [VNPAY validate_response] input_hash:", vnp_SecureHash)

        # So sánh không phân biệt hoa thường
        return vnp_SecureHash.upper() == secure_hash.upper()

    @staticmethod
    def __hmacsha512(key, data):
        # Encode về bytes để hash
        byteKey = key.encode("utf-8")
        byteData = data.encode("utf-8")
        return hmac.new(byteKey, byteData, hashlib.sha512).hexdigest()
