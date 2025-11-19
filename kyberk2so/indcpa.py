from hashlib import sha3_256, sha3_512, shake_128, shake_256
from secrets import token_bytes
from .poly import *
from .params import *

def indcpa_pack_public_key(public_key, seed, paramsK):
	return polyvec_to_bytes(public_key, paramsK) + seed

def indcpa_unpack_public_key(packed_public_key, paramsK):
	if paramsK == 2:
		public_key_polyvec = polyvec_from_bytes(packed_public_key[:paramsPolyvecBytesK512], paramsK)
		seed = packed_public_key[paramsPolyvecBytesK512:]
	elif paramsK == 3:
		public_key_polyvec = polyvec_from_bytes(packed_public_key[:paramsPolyvecBytesK768], paramsK)
		seed = packed_public_key[paramsPolyvecBytesK768:]
	else:
		public_key_polyvec = polyvec_from_bytes(packed_public_key[:paramsPolyvecBytesK1024], paramsK)
		seed = packed_public_key[paramsPolyvecBytesK1024:]
	return public_key_polyvec, seed

def indcpa_pack_private_key(private_key, paramsK):
	return polyvec_to_bytes(private_key, paramsK)

def indcpa_unpack_private_key(packed_private_key, paramsK):
	return polyvec_from_bytes(packed_private_key, paramsK)

def indcpa_pack_ciphertext(b, v, paramsK):
	return polyvec_compress(b, paramsK) + poly_compress(v, paramsK)

def indcpa_unpack_ciphertext(ciphertext, paramsK):
	if paramsK == 2:
		b = polyvec_decompress(ciphertext[:paramsPolyvecCompressedBytesK512], paramsK)
		v = poly_decompress(ciphertext[paramsPolyvecCompressedBytesK512:], paramsK)
	elif paramsK == 3:
		b = polyvec_decompress(ciphertext[:paramsPolyvecCompressedBytesK768], paramsK)
		v = poly_decompress(ciphertext[paramsPolyvecCompressedBytesK768:], paramsK)
	else:
		b = polyvec_decompress(ciphertext[:paramsPolyvecCompressedBytesK1024], paramsK)
		v = poly_decompress(ciphertext[paramsPolyvecCompressedBytesK1024:], paramsK)
	return b, v

def indcpa_rej_uniform(buf, bufl, l):
	r = np.zeros(paramsPolyBytes, dtype=np.int16)
	i = 0
	j = 0
	while i < l and j+3 <= bufl:
		d1 = np.uint16((np.uint16((buf[j])>>0) | (np.uint16(buf[j+1]) << 8)) & 0xFFF)
		d2 = np.uint16((np.uint16((buf[j+1])>>4) | (np.uint16(buf[j+2]) << 4)) & 0xFFF)
		j += 3
		if d1 < np.uint16(paramsQ):
			r[i] = np.int16(d1)
			i += 1
		if i < l and d2 < np.uint16(paramsQ):
			r[i] = np.int16(d2)
			i += 1
	return r, i

def indcpa_gen_matrix(seed, transposed, paramsK):
	r = []
	ctr = 0
	for i in range(paramsK):
		r.append(polyvec_new(paramsK))
		for j in range(paramsK):
			if transposed:
				buf = shake_128(seed + bytes([i,j])).digest(672)
			else:
				buf = shake_128(seed + bytes([j,i])).digest(672)
			r[i][j], ctr = indcpa_rej_uniform(buf[:504], 504, paramsN)
			while ctr < paramsN:
				missing, ctrn = indcpa_rej_uniform(buf[504:672], 168, paramsN-ctr)
				k = ctr
				while k < paramsN:
					r[i][j][k] = missing[k-ctr]
					k+=1
				ctr = ctr + ctrn
	return r

def indcpa_prf(l, key, nonce):
	return shake_256(key + nonce).digest(l)

def indcpa_keypair(paramsK):
	skpv = polyvec_new(paramsK)
	pkpv = polyvec_new(paramsK)
	e = polyvec_new(paramsK)
	buf = sha3_512(token_bytes(paramsSymBytes)).digest()
	public_seed = buf[:paramsSymBytes]
	noise_seed = buf[paramsSymBytes:]
	a = indcpa_gen_matrix(public_seed, False, paramsK)
	nonce = np.uint8(0)
	for i in range(paramsK):
		skpv[i] = poly_get_noise(noise_seed, nonce, paramsK)
		nonce += np.uint8(1)
	for i in range(paramsK):
		e[i] = poly_get_noise(noise_seed, nonce, paramsK)
		nonce += np.uint8(1)
	skpv = polyvec_ntt(skpv, paramsK)
	skpv = polyvec_reduce(skpv, paramsK)
	e = polyvec_ntt(e, paramsK)
	for i in range(paramsK):
		pkpv[i] = poly_to_mont(polyvec_point_wise_acc_montgomery(a[i], skpv, paramsK))
	pkpv = polyvec_add(pkpv, e, paramsK)
	pkpv = polyvec_reduce(pkpv, paramsK)
	return indcpa_pack_private_key(skpv, paramsK), indcpa_pack_public_key(pkpv, public_seed, paramsK)

def indcpa_encrypt(m, public_key, coins, paramsK):
	sp = polyvec_new(paramsK)
	ep = polyvec_new(paramsK)
	bp = polyvec_new(paramsK)
	public_key_polyvec, seed = indcpa_unpack_public_key(public_key, paramsK)
	k = poly_from_msg(m)
	at = indcpa_gen_matrix(seed[:paramsSymBytes], True, paramsK)
	for i in range(paramsK):
		sp[i] = poly_get_noise(coins, np.uint8(i), paramsK)
		ep[i] = poly_get_noise(coins, np.uint8(i+paramsK), 3)
	epp = poly_get_noise(coins, np.uint8(paramsK*2), 3)
	sp = polyvec_ntt(sp, paramsK)
	sp = polyvec_reduce(sp, paramsK)
	for i in range(paramsK):
		bp[i] = polyvec_point_wise_acc_montgomery(at[i], sp, paramsK)
	v = polyvec_point_wise_acc_montgomery(public_key_polyvec, sp, paramsK)
	bp = polyvec_inv_ntt_to_mont(bp, paramsK)
	v = poly_inv_ntt_to_mont(v)
	bp = polyvec_add(bp, ep, paramsK)
	v = poly_add(poly_add(v, epp), k)
	bp = polyvec_reduce(bp, paramsK)
	return indcpa_pack_ciphertext(bp, poly_reduce(v), paramsK)

def indcpa_decrypt(ciphertext, private_key, paramsK):
	bp, v = indcpa_unpack_ciphertext(ciphertext, paramsK)
	private_key_polyvec = indcpa_unpack_private_key(private_key, paramsK)
	bp = polyvec_ntt(bp, paramsK)
	mp = polyvec_point_wise_acc_montgomery(private_key_polyvec, bp, paramsK)
	mp = poly_inv_ntt_to_mont(mp)
	mp = poly_sub(v, mp)
	mp = poly_reduce(mp)
	return poly_to_msg(mp)