import numpy as np

paramsN = np.int64(256)
paramsQ = np.int64(3329)
paramsQDivBy2Ceil = np.uint32(1665)
params2Pow28DivByQ = np.uint32(80635)
params2Pow27DivByQ = np.uint32(40318)
params2Pow31DivByQ = np.uint64(645084)
params2Pow32DivByQ = np.uint64(1290167)
paramsQInv = np.int64(62209)
paramsSymBytes = np.int64(32)
paramsPolyBytes = np.int64(384)
paramsETAK512 = np.int64(3)
paramsETAK768K1024 = np.int64(2)
paramsPolyvecBytesK512 = np.int64(2 * paramsPolyBytes)
paramsPolyvecBytesK768 = np.int64(3 * paramsPolyBytes)
paramsPolyvecBytesK1024 = np.int64(4 * paramsPolyBytes)
paramsPolyCompressedBytesK512 = np.int64(128)
paramsPolyCompressedBytesK768 = np.int64(128)
paramsPolyCompressedBytesK1024 = np.int64(160)
paramsPolyvecCompressedBytesK512 = np.int64(2 * 320)
paramsPolyvecCompressedBytesK768 = np.int64(3 * 320)
paramsPolyvecCompressedBytesK1024 = np.int64(4 * 352)
paramsIndcpaPublicKeyBytesK512 = np.int64(paramsPolyvecBytesK512 + paramsSymBytes)
paramsIndcpaPublicKeyBytesK768 = np.int64(paramsPolyvecBytesK768 + paramsSymBytes)
paramsIndcpaPublicKeyBytesK1024 = np.int64(paramsPolyvecBytesK1024 + paramsSymBytes)
paramsIndcpaSecretKeyBytesK512 = np.int64(2 * paramsPolyBytes)
paramsIndcpaSecretKeyBytesK768 = np.int64(3 * paramsPolyBytes)
paramsIndcpaSecretKeyBytesK1024 = np.int64(4 * paramsPolyBytes)

# Kyber512SKBytes is a constant representing the byte length of private keys in Kyber-512.
Kyber512SKBytes = np.int64(paramsPolyvecBytesK512 + ((paramsPolyvecBytesK512 + paramsSymBytes) + 2*paramsSymBytes))

# Kyber768SKBytes is a constant representing the byte length of private keys in Kyber-768.
Kyber768SKBytes = np.int64(paramsPolyvecBytesK768 + ((paramsPolyvecBytesK768 + paramsSymBytes) + 2*paramsSymBytes))

# Kyber1024SKBytes is a constant representing the byte length of private keys in Kyber-1024.
Kyber1024SKBytes = np.int64(paramsPolyvecBytesK1024 + ((paramsPolyvecBytesK1024 + paramsSymBytes) + 2*paramsSymBytes))

# Kyber512PKBytes is a constant representing the byte length of public keys in Kyber-512.
Kyber512PKBytes = np.int64(paramsPolyvecBytesK512 + paramsSymBytes)

# Kyber768PKBytes is a constant representing the byte length of public keys in Kyber-768.
Kyber768PKBytes = np.int64(paramsPolyvecBytesK768 + paramsSymBytes)

# Kyber1024PKBytes is a constant representing the byte length of public keys in Kyber-1024.
Kyber1024PKBytes = np.int64(paramsPolyvecBytesK1024 + paramsSymBytes)

# Kyber512CTBytes is a constant representing the byte length of ciphertexts in Kyber-512.
Kyber512CTBytes = np.int64(paramsPolyvecCompressedBytesK512 + paramsPolyCompressedBytesK512)

# Kyber768CTBytes is a constant representing the byte length of ciphertexts in Kyber-768.
Kyber768CTBytes = np.int64(paramsPolyvecCompressedBytesK768 + paramsPolyCompressedBytesK768)

# Kyber1024CTBytes is a constant representing the byte length of ciphertexts in Kyber-1024.
Kyber1024CTBytes = np.int64(paramsPolyvecCompressedBytesK1024 + paramsPolyCompressedBytesK1024)

# KyberSSBytes is a constant representing the byte length of shared secrets in Kyber.
KyberSSBytes = np.int64(32)