from hashlib import sha3_256, sha3_512, shake_256
from secrets import token_bytes
from .indcpa import indcpa_encrypt, indcpa_decrypt, indcpa_keypair
from .params import *
np.seterr(over='ignore')

def kem_keypair_512():
	paramsK = 2
	indcpa_private_key, indcpa_public_key = indcpa_keypair(paramsK)
	pkh = sha3_256(indcpa_public_key).digest()
	rnd = token_bytes(paramsSymBytes)
	private_key = indcpa_private_key + indcpa_public_key + pkh + rnd
	return private_key[:Kyber512SKBytes], indcpa_public_key[:Kyber512PKBytes]

def kem_keypair_768():
	paramsK = 3
	indcpa_private_key, indcpa_public_key = indcpa_keypair(paramsK)
	pkh = sha3_256(indcpa_public_key).digest()
	rnd = token_bytes(paramsSymBytes)
	private_key = indcpa_private_key + indcpa_public_key + pkh + rnd
	return private_key[:Kyber768SKBytes], indcpa_public_key[:Kyber768PKBytes]

def kem_keypair_1024():
	paramsK = 4
	indcpa_private_key, indcpa_public_key = indcpa_keypair(paramsK)
	pkh = sha3_256(indcpa_public_key).digest()
	rnd = token_bytes(paramsSymBytes)
	private_key = indcpa_private_key + indcpa_public_key + pkh + rnd
	return private_key[:Kyber1024SKBytes], indcpa_public_key[:Kyber1024PKBytes]

def kem_encrypt_512(public_key):
	paramsK = 2
	buf1 = sha3_256(token_bytes(paramsSymBytes)).digest()
	buf2 = sha3_256(public_key).digest()
	kr = sha3_512(buf1 + buf2).digest()
	ciphertext = indcpa_encrypt(buf1, public_key, kr[paramsSymBytes:], paramsK)
	krc = sha3_256(ciphertext).digest()
	shared_secret = shake_256(kr[:paramsSymBytes] + krc).digest(paramsSymBytes)
	return ciphertext[:Kyber512CTBytes], shared_secret[:KyberSSBytes]

def kem_encrypt_768(public_key):
	paramsK = 3
	buf1 = sha3_256(token_bytes(paramsSymBytes)).digest()
	buf2 = sha3_256(public_key).digest()
	kr = sha3_512(buf1 + buf2).digest()
	ciphertext = indcpa_encrypt(buf1, public_key, kr[paramsSymBytes:], paramsK)
	krc = sha3_256(ciphertext).digest()
	shared_secret = shake_256(kr[:paramsSymBytes] + krc).digest(paramsSymBytes)
	return ciphertext[:Kyber768CTBytes], shared_secret[:KyberSSBytes]

def kem_encrypt_1024(public_key):
	paramsK = 4
	buf1 = sha3_256(token_bytes(paramsSymBytes)).digest()
	buf2 = sha3_256(public_key).digest()
	kr = sha3_512(buf1 + buf2).digest()
	ciphertext = indcpa_encrypt(buf1, public_key, kr[paramsSymBytes:], paramsK)
	krc = sha3_256(ciphertext).digest()
	shared_secret = shake_256(kr[:paramsSymBytes] + krc).digest(paramsSymBytes)
	return ciphertext[:Kyber1024CTBytes], shared_secret[:KyberSSBytes]

def kem_decrypt_512(ciphertext, private_key):
	paramsK = 2
	indcpa_private_key = private_key[:paramsIndcpaSecretKeyBytesK512]
	pki = paramsIndcpaSecretKeyBytesK512 + paramsIndcpaPublicKeyBytesK512
	public_key = private_key[paramsIndcpaSecretKeyBytesK512:pki]
	buf = indcpa_decrypt(ciphertext, indcpa_private_key, paramsK)
	ski = Kyber512SKBytes - 2*paramsSymBytes
	kr = bytearray(sha3_512(buf + private_key[ski:ski+paramsSymBytes]).digest())
	krh = sha3_256(ciphertext).digest()
	# constant time compare will go here (something like this)
	# compare = indcpa_encrypt(buf, public_key, bytes(kr[paramsSymBytes:]), paramsK)
	# fail = constant_time_compare(ciphertext, compare)
	# for i in range(paramsSymBytes):
	# 	skx = private_key[:Kyber512SKBytes-paramsSymBytes+i]
	# 	kr[i] = kr[i] ^ (fail & (kr[i] ^ skx[i]))
	shared_secret = shake_256(bytes(kr[:paramsSymBytes]) + krh[:]).digest(KyberSSBytes)
	return shared_secret

def kem_decrypt_768(ciphertext, private_key):
	paramsK = 3
	indcpa_private_key = private_key[:paramsIndcpaSecretKeyBytesK768]
	pki = paramsIndcpaSecretKeyBytesK768 + paramsIndcpaPublicKeyBytesK768
	public_key = private_key[paramsIndcpaSecretKeyBytesK768:pki]
	buf = indcpa_decrypt(ciphertext, indcpa_private_key, paramsK)
	ski = Kyber768SKBytes - 2*paramsSymBytes
	kr = bytearray(sha3_512(buf + private_key[ski:ski+paramsSymBytes]).digest())
	krh = sha3_256(ciphertext).digest()
	# constant time compare will go here (something like this)
	# compare = indcpa_encrypt(buf, public_key, bytes(kr[paramsSymBytes:]), paramsK)
	# fail = constant_time_compare(ciphertext, compare)
	# for i in range(paramsSymBytes):
	# 	skx = private_key[:Kyber768SKBytes-paramsSymBytes+i]
	# 	kr[i] = kr[i] ^ (fail & (kr[i] ^ skx[i]))
	shared_secret = shake_256(bytes(kr[:paramsSymBytes]) + krh[:]).digest(KyberSSBytes)
	return shared_secret

def kem_decrypt_1024(ciphertext, private_key):
	paramsK = 4
	indcpa_private_key = private_key[:paramsIndcpaSecretKeyBytesK1024]
	pki = paramsIndcpaSecretKeyBytesK1024 + paramsIndcpaPublicKeyBytesK1024
	public_key = private_key[paramsIndcpaSecretKeyBytesK1024:pki]
	buf = indcpa_decrypt(ciphertext, indcpa_private_key, paramsK)
	ski = Kyber1024SKBytes - 2*paramsSymBytes
	kr = bytearray(sha3_512(buf + private_key[ski:ski+paramsSymBytes]).digest())
	krh = sha3_256(ciphertext).digest()
	# constant time compare will go here (something like this)
	# compare = indcpa_encrypt(buf, public_key, bytes(kr[paramsSymBytes:]), paramsK)
	# fail = constant_time_compare(ciphertext, compare)
	# for i in range(paramsSymBytes):
	# 	skx = private_key[:Kyber1024SKBytes-paramsSymBytes+i]
	# 	kr[i] = kr[i] ^ (fail & (kr[i] ^ skx[i]))
	shared_secret = shake_256(bytes(kr[:paramsSymBytes]) + krh[:]).digest(KyberSSBytes)
	return shared_secret


# Example Usage
if __name__ == '__main__':
	import time

	# Start the timer
	start_time = time.time()

	# Example Usage
	sk, pk = kem_keypair_512()
	ct, ss_a = kem_encrypt_512(pk)
	ss_b = kem_decrypt_512(ct, sk)

	# Stop the timer
	end_time = time.time()

	# Calculate the duration in milliseconds
	duration_ms = (end_time - start_time) * 1000

	print('Key Exchange Success:', ss_a == ss_b)
	print(f"Total execution time: {duration_ms:.2f} ms")