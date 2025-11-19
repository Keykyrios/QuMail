from .params import *
from .ntt import *

def poly_compress(a, paramsK):
	t = np.zeros(8, dtype=np.uint8)
	a = poly_c_sub_q(a)
	rr = 0
	if paramsK in [2,3]:
		r = np.zeros(paramsPolyCompressedBytesK768, dtype=np.uint8)
		for i in range(paramsN//8):
			for j in range(8):
				t[j] = np.uint8((((np.uint32(a[8*i+j]) << 4) + paramsQDivBy2Ceil) * params2Pow28DivByQ) >> 28)
			r[rr+0] = t[0] | (t[1] << 4)
			r[rr+1] = t[2] | (t[3] << 4)
			r[rr+2] = t[4] | (t[5] << 4)
			r[rr+3] = t[6] | (t[7] << 4)
			rr += 4
	else:
		r = np.zeros(paramsPolyCompressedBytesK1024, dtype=np.uint8)
		for i in range(paramsN//8):
			for j in range(8):
				t[j] = np.uint8((((np.uint32(a[8*i+j]) << 5) + (paramsQDivBy2Ceil - 1)) * params2Pow27DivByQ) >> 27)
			r[rr+0] = (t[0] >> 0) | (t[1] << 5)
			r[rr+1] = (t[1] >> 3) | (t[2] << 2) | (t[3] << 7)
			r[rr+2] = (t[3] >> 1) | (t[4] << 4)
			r[rr+3] = (t[4] >> 4) | (t[5] << 1) | (t[6] << 6)
			r[rr+4] = (t[6] >> 2) | (t[7] << 3)
			rr += 5
	return bytes(r)

def poly_decompress(a, paramsK):
	r = np.zeros(paramsPolyBytes, dtype=np.int16)
	t = np.zeros(8, dtype=np.uint8)
	aa = 0
	if paramsK in [2,3]:
		for i in range(paramsN//2):
			r[2*i+0] = np.int16(((np.uint16(a[aa] & 15) * np.uint16(paramsQ)) + 8) >> 4)
			r[2*i+1] = np.int16(((np.uint16(a[aa] >> 4) * np.uint16(paramsQ)) + 8) >> 4)
			aa += 1
	else:
		for i in range(paramsN//8):
			t[0] = (a[aa+0] >> 0)
			t[1] = (a[aa+0] >> 5) | (a[aa+1] << 3)
			t[2] = (a[aa+1] >> 2)
			t[3] = (a[aa+1] >> 7) | (a[aa+2] << 1)
			t[4] = (a[aa+2] >> 4) | (a[aa+3] << 4)
			t[5] = (a[aa+3] >> 1)
			t[6] = (a[aa+3] >> 6) | (a[aa+4] << 2)
			t[7] = (a[aa+4] >> 3)
			aa += 5
			for j in range(8):
				r[8*i+j] = np.int16(((np.uint32(t[j]&31) * np.uint32(paramsQ)) + 16) >> 5)
	return r

def poly_to_bytes(a):
	r = bytearray(paramsPolyBytes)
	a = poly_c_sub_q(a)
	for i in range(paramsN//2):
		t0 = np.uint16(a[2*i])
		t1 = np.uint16(a[2*i+1])
		r[3*i+0] = np.uint8(t0 >> 0)
		r[3*i+1] = np.uint8(t0 >> 8) | np.uint8(t1 << 4)
		r[3*i+2] = np.uint8(t1 >> 4)
	return bytes(r)

def poly_from_bytes(a):
	r = np.zeros(paramsPolyBytes, dtype=np.int16)
	for i in range(paramsN//2):
		r[2*i] = np.int16(((np.uint16(a[3*i+0]) >> 0) | (np.uint16(a[3*i+1]) << 8)) & 0xFFF)
		r[2*i+1] = np.int16(((np.uint16(a[3*i+1]) >> 4) | (np.uint16(a[3*i+2]) << 4)) & 0xFFF)
	return r

def poly_from_msg(msg):
	r = np.zeros(paramsPolyBytes, dtype=np.int16)
	for i in range(paramsN//8):
		for j in range(8):
			mask = -np.int16((msg[i] >> j) & 1)
			r[8*i+j] = mask & np.int16((paramsQ+1)//2)
	return r

def poly_to_msg(a):
	msg = np.zeros(paramsSymBytes, dtype=np.uint8)
	a = poly_c_sub_q(a)
	for i in range(paramsN//8):
		for j in range(8):
			t = (np.uint32(a[8*i+j]) << 1) + paramsQDivBy2Ceil
			t = ((t * params2Pow28DivByQ) >> 28) & 1
			msg[i] |= np.uint8(t << j)
	return bytes(msg)

def poly_get_noise(seed, nonce, paramsK):
	from .indcpa import indcpa_prf
	if paramsK == 2:
		l = paramsETAK512 * paramsN // 4
		p = indcpa_prf(l, seed, nonce)
	else:
		l = paramsETAK768K1024 * paramsN // 4
		p = indcpa_prf(l, seed, nonce)
	return byteops_cbd(p, paramsK)

def poly_ntt(r):
	return ntt(r)

def poly_inv_ntt_to_mont(r):
	return ntt_inv(r)

def poly_base_mul_montgomery(a, b):
	for i in range(paramsN//4):
		a[4*i+0], a[4*i+1] = ntt_base_mul(a[4*i+0], a[4*i+1], b[4*i+0], b[4*i+1], nttZetas[64+i])
		a[4*i+2], a[4*i+3] = ntt_base_mul(a[4*i+2], a[4*i+3], b[4*i+2], b[4*i+3], -nttZetas[64+i])
	return a

def poly_to_mont(r):
	f = np.int16((np.uint64(1) << np.uint64(32)) % np.uint64(paramsQ))
	for i in range(paramsN):
		r[i] = byteops_montgomery_reduce(np.int32(r[i]) * np.int32(f))
	return r

def poly_reduce(r):
	vectorized_byteops_barrett_reduce = np.vectorize(byteops_barrett_reduce)
	return vectorized_byteops_barrett_reduce(r)

def poly_c_sub_q(r):
	vectorized_byteops_c_sub_q = np.vectorize(byteops_c_sub_q)
	return vectorized_byteops_c_sub_q(r)

def poly_add(a, b):
	return a + b

def poly_sub(a, b):
	return a - b

def polyvec_new(paramsK):
	return [np.zeros(paramsPolyBytes, dtype=np.int16) for _ in range(paramsK)]

def polyvec_compress(a, paramsK):
	a = polyvec_c_sub_q(a, paramsK)
	rr = 0
	if paramsK in [2,3]:
		t = np.zeros(4, dtype=np.uint16)
		r = np.zeros(paramsPolyvecCompressedBytesK512, dtype=np.uint8) if paramsK == 2 else np.zeros(paramsPolyvecCompressedBytesK768, dtype=np.uint8)
		for i in range(paramsK):
			for j in range(paramsN//4):
				for k in range(4):
					t[k] = np.uint16(((((np.uint64(a[i][4*j+k]) << np.uint64(10)) + np.uint64(paramsQDivBy2Ceil)) * params2Pow32DivByQ) >> np.uint64(32)) & np.uint64(0x3ff))
				r[rr+0] = np.uint8(t[0] >> 0)
				r[rr+1] = np.uint8((t[0] >> 8) | (t[1] << 2))
				r[rr+2] = np.uint8((t[1] >> 6) | (t[2] << 4))
				r[rr+3] = np.uint8((t[2] >> 4) | (t[3] << 6))
				r[rr+4] = np.uint8((t[3] >> 2))
				rr += 5
	else:
		t = np.zeros(8, dtype=np.uint16)
		r = np.zeros(paramsPolyvecCompressedBytesK1024, dtype=np.uint8)
		for i in range(paramsK):
			for j in range(paramsN//8):
				for k in range(8):
					t[k] = np.uint16(((((np.uint64(a[i][8*j+k]) << np.uint64(11)) + np.uint64(paramsQDivBy2Ceil-1)) * params2Pow31DivByQ) >> np.uint64(31)) & np.uint64(0x7ff))
				r[rr+0] = np.uint8((t[0] >> 0))
				r[rr+1] = np.uint8((t[0] >> 8) | (t[1] << 3))
				r[rr+2] = np.uint8((t[1] >> 5) | (t[2] << 6))
				r[rr+3] = np.uint8((t[2] >> 2))
				r[rr+4] = np.uint8((t[2] >> 10) | (t[3] << 1))
				r[rr+5] = np.uint8((t[3] >> 7) | (t[4] << 4))
				r[rr+6] = np.uint8((t[4] >> 4) | (t[5] << 7))
				r[rr+7] = np.uint8((t[5] >> 1))
				r[rr+8] = np.uint8((t[5] >> 9) | (t[6] << 2))
				r[rr+9] = np.uint8((t[6] >> 6) | (t[7] << 5))
				r[rr+10] = np.uint8((t[7] >> 3))
				rr += 11
	return bytes(r)

def polyvec_decompress(a, paramsK):
	r = polyvec_new(paramsK)
	aa = 0
	if paramsK in [2, 3]:
		t = np.zeros(4, dtype=np.uint16)
		for i in range(paramsK):
			for j in range(paramsN//4):
				t[0] = (np.uint16(a[aa+0]) >> 0) | (np.uint16(a[aa+1]) << 8)
				t[1] = (np.uint16(a[aa+1]) >> 2) | (np.uint16(a[aa+2]) << 6)
				t[2] = (np.uint16(a[aa+2]) >> 4) | (np.uint16(a[aa+3]) << 4)
				t[3] = (np.uint16(a[aa+3]) >> 6) | (np.uint16(a[aa+4]) << 2)
				aa += 5
				for k in range(4):
					r[i][4*j+k] = np.int16((np.uint32(t[k] & 0x3FF)*np.uint32(paramsQ) + 512) >> 10)
	else:
		t = np.zeros(8, dtype=np.uint16)
		for i in range(paramsK):
			for j in range(paramsN//8):
				t[0] = (np.uint16(a[aa+0]) >> 0) | (np.uint16(a[aa+1]) << 8)
				t[1] = (np.uint16(a[aa+1]) >> 3) | (np.uint16(a[aa+2]) << 5)
				t[2] = (np.uint16(a[aa+2]) >> 6) | (np.uint16(a[aa+3]) << 2) | (np.uint16(a[aa+4]) << 10)
				t[3] = (np.uint16(a[aa+4]) >> 1) | (np.uint16(a[aa+5]) << 7)
				t[4] = (np.uint16(a[aa+5]) >> 4) | (np.uint16(a[aa+6]) << 4)
				t[5] = (np.uint16(a[aa+6]) >> 7) | (np.uint16(a[aa+7]) << 1) | (np.uint16(a[aa+8]) << 9)
				t[6] = (np.uint16(a[aa+8]) >> 2) | (np.uint16(a[aa+9]) << 6)
				t[7] = (np.uint16(a[aa+9]) >> 5) | (np.uint16(a[aa+10]) << 3)
				aa += 11
				for k in range(8):
					r[i][8*j+k] = np.int16((np.uint32(t[k]&0x7FF)*np.uint32(paramsQ) + 1024) >> 11)
	return r

def polyvec_to_bytes(a, paramsK):
	r = b''
	for i in range(paramsK):
		r = r + poly_to_bytes(a[i])
	return r

def polyvec_from_bytes(a, paramsK):
	r = polyvec_new(paramsK)
	for i in range(paramsK):
		start = i * paramsPolyBytes
		end = (i + 1) * paramsPolyBytes
		r[i] = poly_from_bytes(a[start:end])
	return r

def polyvec_ntt(r, paramsK):
	for i in range(paramsK):
		r[i] = poly_ntt(r[i])
	return r

def polyvec_inv_ntt_to_mont(r, paramsK):
	for i in range(paramsK):
		r[i] = poly_inv_ntt_to_mont(r[i])
	return r

def polyvec_point_wise_acc_montgomery(a, b, paramsK):
	r = poly_base_mul_montgomery(a[0], b[0])
	for i in range(1, paramsK):
		t = poly_base_mul_montgomery(a[i], b[i])
		r = poly_add(r, t)
	return poly_reduce(r)

def polyvec_reduce(r, paramsK):
	for i in range(paramsK):
		r[i] = poly_reduce(r[i])
	return r

def polyvec_c_sub_q(r, paramsK):
	for i in range(paramsK):
		r[i] = poly_c_sub_q(r[i])
	return r

def polyvec_add(a, b, paramsK):
	for i in range(paramsK):
		a[i] = poly_add(a[i], b[i])
	return a