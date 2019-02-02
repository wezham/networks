import string 

print("#!/bin/bash")

print('if [ "$1" = "1" ]')
print("then")

for index,letter in enumerate(list(string.ascii_uppercase)[:6]):
    print(f'osascript -e \'tell application "Terminal" to do script "python3 /Users/wesleyhamburger/Desktop/3331/assignment/networks/Lsr.py {letter} 500{index} /Users/wesleyhamburger/Desktop/3331/assignment/networks/test1/config{letter}.txt"\'')

print("fi")
print("#######################################################\n\n")

print('if [ "$1" = "2" ]')
print("then")
for index,letter in enumerate(list(string.ascii_uppercase)[:10]):
   #print(f'osascript -e \'tell application "Terminal" to do script "python3 /Users/wesleyhamburger/Desktop/3331/assignment/Lsr.py {letter} 500{index} /Users/wesleyhamburger/Desktop/3331/assignment/test2/config{letter}.txt"\'')
   print(f'osascript -e \'tell application "Terminal" to do script "python3 /Users/wesleyhamburger/Desktop/3331/assignment/networks/Lsr.py {letter} 500{index} /Users/wesleyhamburger/Desktop/3331/assignment/networks/test2/config{letter}.txt"\'')
print("fi")
