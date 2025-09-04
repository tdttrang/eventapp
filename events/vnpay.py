# import hashlib
# import hmac
# import urllib.parse
#
# class vnpay:
#     def __init__(self):
#         # requestData: dữ liệu gửi đi cho VNPAY
#         self.requestData = {}
#         # responseData: dữ liệu callback / IPN nhận về từ VNPAY
#         self.responseData = {}
#
#     def get_payment_url(self, vnpay_payment_url, secret_key):
#         # Sắp xếp tham số theo key
#         inputData = sorted(self.requestData.items())
#         hashData = ""
#         queryString = ""
#
#         # Ghép chuỗi query và hashData
#         for idx, (key, val) in enumerate(inputData):
#             if idx == 0:
#                 hashData = f"{key}={val}"
#                 queryString = f"{key}={urllib.parse.quote(str(val), safe='')}"
#             else:
#                 hashData += f"&{key}={val}"
#                 queryString += f"&{key}={urllib.parse.quote(str(val), safe='')}"
#
#         # Sinh SecureHash bằng HMAC SHA512
#         secure_hash = self.__hmacsha512(secret_key, hashData)
#
#         # Log để debug
#         print(">>> [VNPAY get_payment_url] hashData:", hashData)
#         print(">>> [VNPAY get_payment_url] secure_hash:", secure_hash)
#
#         # Trả về URL hoàn chỉnh
#         return f"{vnpay_payment_url}?{queryString}&vnp_SecureHash={secure_hash}"
#
#     def validate_response(self, secret_key):
#         # Lấy secure hash từ response
#         vnp_SecureHash = self.responseData.get("vnp_SecureHash", "")
#
#         # Copy dữ liệu để không làm thay đổi gốc
#         data = self.responseData.copy()
#
#         # Xóa hash params để tính lại
#         data.pop("vnp_SecureHash", None)
#         data.pop("vnp_SecureHashType", None)
#
#         # Sắp xếp tham số theo key
#         inputData = sorted(data.items())
#         hashData = "&".join([f"{key}={val}" for key, val in inputData])
#
#         # Tính lại hash
#         secure_hash = self.__hmacsha512(secret_key, hashData)
#
#         # Log để debug
#         print(">>> [VNPAY validate_response] hashData:", hashData)
#         print(">>> [VNPAY validate_response] secure_hash:", secure_hash)
#         print(">>> [VNPAY validate_response] input_hash:", vnp_SecureHash)
#
#         # So sánh không phân biệt hoa thường
#         return vnp_SecureHash.upper() == secure_hash.upper()
#
#     @staticmethod
#     def __hmacsha512(key, data):
#         # Encode về bytes để hash
#         byteKey = key.encode("utf-8")
#         byteData = data.encode("utf-8")
#         return hmac.new(byteKey, byteData, hashlib.sha512).hexdigest()

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

        # Chuỗi hashData để ký (không encode)
        hashData = "&".join([f"{k}={v}" for k, v in inputData])

        # Chuỗi queryString để build URL (phải encode value, thay %20 thành +)
        queryString = "&".join(
            [f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in inputData]
        )

        # ✅ Tính chữ ký HMAC SHA512
        secure_hash = hmac.new(
            secret_key.encode("utf-8"),
            hashData.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()

        # Append secure hash
        full_url = (
            f"{vnpay_payment_url}?{queryString}"
            f"&vnp_SecureHashType=HMACSHA512&vnp_SecureHash={secure_hash}"
        )

        # Log debug
        print(">>> [VNPAY get_payment_url] hashData:", hashData)
        print(">>> [VNPAY get_payment_url] queryString:", queryString)
        print(">>> [VNPAY get_payment_url] secure_hash:", secure_hash)

        return full_url

    def validate_response(self, secret_key):
        """
        Validate chữ ký khi nhận dữ liệu từ VNPAY (return / ipn)
        """
        vnp_SecureHash = self.responseData.get("vnp_SecureHash")
        vnp_SecureHashType = self.responseData.get("vnp_SecureHashType")

        # Copy data rồi loại bỏ SecureHash và SecureHashType
        inputData = self.responseData.copy()
        inputData.pop("vnp_SecureHash", None)
        inputData.pop("vnp_SecureHashType", None)

        # Sắp xếp key để hash
        inputData = sorted(inputData.items())
        hashData = "&".join([f"{k}={v}" for k, v in inputData])

        # Tính hash lại
        hashValue = hmac.new(
            secret_key.encode("utf-8"),
            hashData.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()

        # Log debug
        print(">>> [VNPAY validate_response] hashData:", hashData)
        print(">>> [VNPAY validate_response] calculated hash:", hashValue)
        print(">>> [VNPAY validate_response] vnp_SecureHash:", vnp_SecureHash)
        print(">>> [VNPAY validate_response] vnp_SecureHashType:", vnp_SecureHashType)

        return vnp_SecureHash == hashValue
