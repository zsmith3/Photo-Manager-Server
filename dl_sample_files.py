import sys

print(f"TEST CONTENT, arg={sys.argv[0]}")

# Test persistence of file
f = open("test.txt", "w")
f.write(f"TEST CONTENT, arg={sys.argv[0]}")
f.close()
