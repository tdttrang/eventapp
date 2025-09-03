import hashlib
import hmac
import urllib.parse

class vnpay:
    def __init__(self):
        # requestData: lưu dữ liệu để tạo URL thanh toán
        self.requestData = {}
        # responseData: lưu dữ liệu trả về từ VNPAY (Return / IPN)
        self.responseData = {}

    def get_payment_url(self, vnpay_payment_url, secret_key):
        # Sắp xếp params theo key tên tăng dần
        inputData = sorted(self.requestData.items())
        hashData = ""
        queryString = ""

        # Tạo hashData (dùng để tạo chữ ký) và queryString (encode để gửi)
        for idx, (key, val) in enumerate(inputData):
            if idx == 0:
                hashData = f"{key}={val}"
                queryString = f"{key}={urllib.parse.quote(str(val), safe='')}"
            else:
                hashData += f"&{key}={val}"
                queryString += f"&{key}={urllib.parse.quote(str(val), safe='')}"

        # Sinh chữ ký HMAC SHA512
        secure_hash = self._hmacsha512(secret_key, hashData)

        # Log để debug so sánh với VNPAY
        print(">>> [VNPAY get_payment_url] hashData:", hashData)
        print(">>> [VNPAY get_payment_url] secure_hash:", secure_hash)

        # Trả về URL thanh toán hoàn chỉnh
        return f"{vnpay_payment_url}?{queryString}&vnp_SecureHash={secure_hash}"

    def validate_response(self, secret_key):
        # Lấy vnp_SecureHash từ response
        vnp_SecureHash = self.responseData.get("vnp_SecureHash", "")

        # Copy data để không ảnh hưởng dict gốc
        data = self.responseData.copy()
        data.pop("vnp_SecureHash", None)
        data.pop("vnp_SecureHashType", None)

        # Sắp xếp lại để tính hash
        inputData = sorted(data.items())
        hashData = ""
        for idx, (key, val) in enumerate(inputData):
            if idx == 0:
                hashData = f"{key}={val}"
            else:
                hashData += f"&{key}={val}"

        # Tính lại hash
        secure_hash = self._hmacsha512(secret_key, hashData)

        # Log để check khớp
        print(">>> [VNPAY validate_response] hashData:", hashData)
        print(">>> [VNPAY validate_response] secure_hash:", secure_hash)
        print(">>> [VNPAY validate_response] input_hash:", vnp_SecureHash)

        print(">>> [VNPAY validate_response] full responseData:", self.responseData)
        return vnp_SecureHash.upper() == secure_hash.upper()

    @staticmethod
    def _hmacsha512(key, data):
        return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha512).hexdigest()
