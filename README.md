# redisMessenger
Command line messaging app 
 - using a redis database


IMPORTANT:
- REDIS SERVER IS NO LONGER RUNNING
- if you are going to change the redis_connection
please dont forget to set decode_responses=True
e.g redis.StrictRedis(host="0.tcp.ngrok.io",port=16931, decode_responses=True)
if you dont do this the formatting will be wrong my code will not work


features of command line interface: 

1 - add new user. 
- e.g 'python task3.py reg-user {name} {user_name}'
- the implementation checks if the username is already taken

2 - show list of users. 
- e.g 'python task3.py show-users' will give you a list of all the users keys
- e.g 'python task3.py show-users -u' will give you a list of all the usernames

3 - run the application
- e.g 'python task3.py run-as {username}'
- this will start the application as if logged in by a specified user.
- if the -l flag is set. e.g 'python task3.py run-as {username} -l' this will run the app in multithreaded mode.
- while running in multithreaded mode, you will get live update of the current open chat, live updates on the notifications.
