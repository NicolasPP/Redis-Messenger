import redis
import threading
import time
import click
import os



redis_connection = redis.StrictRedis(host="0.tcp.ngrok.io",port=16931, decode_responses=True)
print(redis_connection)
# redis_connection = redis.StrictRedis(port=6379, decode_responses=True) #### for working locally ####
NEXT_USERID = 'next_userid'
USERNAME = 'username'
NAME = 'name'


#_________ COMMAND LINE INTERFACE _________#

@click.group()
def main():
	"""
	Command line interface messaging app \n
	Using redis Database
	"""
	pass


@main.command(help='run app as specified user')
@click.argument('user_name')
@click.option('-l', is_flag=True)
def run_as(user_name, l):
	if not is_username_registered(user_name):
		click.echo(click.style(f'user: {user_name} not registered yet', fg='red', bold=True))
		return
	lock = threading.Lock()
	user_dict, uid = get_dict_username(user_name)
	messaging_app = App(user_dict, uid, lock, redis_connection)
	if l: messaging_app.toggle_state('listen')
	thread_app = threading.Thread(target=messaging_app.run)
	listen_thread = threading.Thread(target=messaging_app.listen)
	thread_app.start()
	if l: listen_thread.start()
	if l: listen_thread.join()
	thread_app.join()

@main.command(help='get list of users -u to show username')
@click.option('-u', is_flag=True)
def show_users(u):
	if u:
		users = get_users_dict()
		for user in users:
			click.echo(user[USERNAME])
	else:
		users = get_users()
		click.echo(users)

@main.command('reg-user', help='register new user')
@click.argument('name')
@click.argument('user_name')
def register_new_user(name, user_name):
	if is_username_registered(user_name):
		click.echo(click.style(f'user {user_name} already exists', fg='red', bold='True'))

	user_key = new_user_key()
	new_user = f'user{user_key}'
	redis_connection.hset(new_user, 'name', name)
	redis_connection.hset(new_user, 'username', user_name)
	redis_connection.set(NEXT_USERID, user_key + 1)


#_________ helper functions _________#
def is_username_registered(user_name):
	users = get_users_dict()
	for user in users:
		if user[USERNAME] == user_name: return True
	return False

def get_users():
	return redis_connection.keys('user*')

def get_users_dict():
	users_dict = []
	users = get_users()
	for user in users:
		user_info = redis_connection.hgetall(user)
		users_dict.append(user_info)
	return users_dict

def get_dict_username(user_name):
	users = get_users()
	for user in users:
		info = redis_connection.hgetall(user)
		uid = int(user[4:])
		if info[USERNAME] == user_name:
			return info, uid
	click.echo(click.style(f'user: {user_name} not found', fg='red', bold=True))

def get_chat_members(chat_name, sender_name = False):
	members = [redis_connection.hgetall(user)[NAME] for user in chat_name.split("_")[1:]]
	if sender_name and sender_name in members: members.remove(sender_name)
	return members

def new_user_key():
	return int(redis_connection.get(NEXT_USERID))

def get_chat_name(members_id):
	members_id.sort()
	chat_name = f'conversation'
	for m_id in members_id:
		chat_name+=f'_user{m_id}'
	return chat_name

def create_notification(chat_name, sender_id, message): 
	return f'{chat_name}/user{sender_id}/{message}'

def send_notifications(members_id, sender_id, chat_name, message):
	notification = create_notification(chat_name, sender_id, message)
	for m_id in members_id:
		if m_id != sender_id:
			notification_name = f'notification_user{m_id}'
			redis_connection.rpush(notification_name, notification)

def send_message(members_id, sender_id, message):
	chat_name = get_chat_name(members_id)
	m = f'user{sender_id}:{message}'
	redis_connection.rpush(chat_name, m)
	send_notifications(members_id, sender_id, chat_name, message)


class App:
	def __init__(self, user_dict, uid, lock, rc):
		self.user_dict = user_dict
		self.lock = lock
		self.test = 0
		self.redis_connection = rc
		self.uid = uid
		self.notifications = self.get_notification_list()

		self.display_notification = False
		self.state = {
			'menu': True,
			'notification': False,
			'start_chat': False,
			'open_chat': False,
			'chat': False,
			'chat_with' : False,
			'listen' : False,
			'done' : False,
		}

		
		self.current_convo = None

	# __ MAIN APP LOOP __ #
	def run(self):
		while not self.state['done']:
			self.iterate()

	def iterate(self, invalidate=False):
		self.draw_menu(invalidate)
		self.draw_notification(invalidate)
		self.draw_start_chat(invalidate)
		self.draw_open_chat(invalidate)
		self.draw_chat(invalidate)

	# __ DRAW FUCNTIONS __ #		
	def draw_menu(self, invalidate):
		if self.state['menu']:
			os.system('cls')
			self.lock.acquire()
			click.echo(f'Running as user: {self.user_dict[USERNAME]}')
			click.echo(f'Notifications - [{len(self.notifications)}]')
			click.echo('=================')
			click.echo(f'QUIT: 1')
			click.echo(f'View notifications : 2')
			click.echo(f'Start chat: 3')
			click.echo(f'Open chat: 4')
			self.lock.release()
			if not invalidate:
				u_input = self.get_user_input()
				self.parse_menu_input(u_input)

	def draw_notification(self, invalidate):
		if self.state['notification']:
			os.system('cls')
			self.lock.acquire()
			for n in self.notifications:
				chat, sender, message = tuple(n.split('/', 2))
				sender_name = self.redis_connection.hgetall(sender)[NAME]
				members = get_chat_members(chat, sender_name)
				click.echo(f'{sender_name} sent message to {"-".join(members)}')
				click.echo(f'message: {message}')
				click.echo('-----------------------------------------')
			self.lock.release()
			click.echo('=================')
			click.echo("back to menu : 1")
			click.echo("clear notifications: 2")
			if not invalidate:
				u_input = self.get_user_input()
				self.parse_notification_input(u_input)

	def draw_start_chat(self, invalidate):
		if self.state['start_chat']:
			os.system('cls')
			header = click.style(f'NAME---:---ID   ', bold = True)
			click.echo(header)
			for user in self.redis_connection.keys('user*'):
				user_id = int(user[4:])
				user_name = self.redis_connection.hgetall(user)[NAME]
				info = f'{user_name} - {user_id}'
				click.echo(info)
				click.echo('-----------------------')
			click.echo('=================')
			click.echo('back to menu: 1')
			click.echo('start chat: 2')
			if not invalidate:
				u_input = self.get_user_input()
				self.parse_start_chat_input(u_input)

	def draw_open_chat(self, invalidate):
		if self.state['open_chat']:
			os.system('cls')
			conversations = self.get_convos()
			for index, convo in enumerate(conversations):
				sender_name = self.redis_connection.hgetall(f'user{self.uid}')[NAME]
				members = get_chat_members(convo, sender_name)
				click.echo(f'[{"_".join(members)}] id: {index}')
			click.echo('=================')
			click.echo('back to menu: 1')
			click.echo('open chat: 2')

			if not invalidate:
				u_input = self.get_user_input()
				self.parse_open_chat_input(u_input, conversations)

	def draw_chat(self, invalidate):
		if self.state['chat']:
			os.system('cls')
			if self.current_convo == None:
				click.echo(click.style('current chat not set, try opening or starting a chat first', bold=True))
				return

			messages = redis_connection.lrange(self.current_convo, 0 , -1)
			for u_msg in messages:
				user, msg = tuple(u_msg.split(":"))
				user_name = self.redis_connection.hgetall(user)[NAME] if user != f'user{self.uid}' else 'ME'
				click.echo(f'{user_name} : {msg}')
			click.echo('=================')
			click.echo('back to menu: 1')
			click.echo('send a message: 2')

			if not invalidate:
				u_input = self.get_user_input()
				self.parse_chat_input(u_input)
 

	# __ PARSE FUCNTIONS __ #

	def parse_menu_input(self, u_input):
		if u_input == '1': self.quit()
		elif u_input == '2': 
			self.toggle_state('notification')
			self.toggle_state('menu')
		elif u_input == '3': 
			self.toggle_state('start_chat')
			self.toggle_state('menu')
		elif u_input == '4':
			self.toggle_state('open_chat')
			self.toggle_state('menu')
		else:
			click.echo(click.style(f'input: {u_input} not valid'))
			time.sleep(5)

	def parse_notification_input(self, u_input):
		if u_input == '1': 
			self.toggle_state('notification')
			self.toggle_state('menu')
		elif u_input == '2':
			self.clear_notifications()
		else:
			click.echo(click.style(f'input: {u_input} not valid'))
			time.sleep(5)

	def parse_start_chat_input(self, u_input):
		if u_input == '1':
			self.toggle_state('start_chat')
			self.toggle_state('menu')
		elif u_input == '2':
			chat_members = input('start chat with user ids:')
			first_message = input('message: ')
			chat_members = chat_members.strip().split(" ")
			chat_members.append(self.uid)
			chat_members = [int(x) for x in chat_members]
			send_message(chat_members, self.uid, first_message)
		else:
			click.echo(click.style(f'input: {u_input} not valid', fg='red', bold=True))
			time.sleep(5)

	def parse_open_chat_input(self, u_input, convos):
		u_input = u_input.strip()
		if u_input == '1':
			self.toggle_state('open_chat')
			self.toggle_state('menu')
		elif u_input == '2':
			chat_index = int(input('pick chat id:'))
			if chat_index < len(convos):
				self.current_convo = convos[chat_index]
			else:
				click.echo(click.style(f'chat index: {chat_index} doesnt exist', fg='red', bold=True))
				time.sleep(5)
				return


			self.toggle_state('open_chat')
			self.toggle_state('chat')
		else:
			click.echo(click.style(f'input: {u_input} not valid', fg='red', bold=True))
			time.sleep(5)
	
	def parse_chat_input(self, u_input):
		u = u_input.strip()
		if u_input == '1':
			self.toggle_state('chat')
			self.toggle_state('open_chat')
		elif u_input == '2':
			message = input('message:' )
			chat_members = [int(uid[4:]) for uid in self.current_convo.split('_')[1:]]
			send_message(chat_members, self.uid, message)
			self.draw_chat(invalidate = True)
		else:
			click.echo(click.style(f'input: {u_input} not valid', fg='red', bold=True))
			time.sleep(5)


	# __ HELPER FUCNTIONS __ #
	def clear_notifications(self):
		notification_name = f'notification_user{self.uid}'
		n_size = self.redis_connection.llen(notification_name)
		for i in range(n_size):
			self.redis_connection.rpop(notification_name)
		self.notifications = self.get_notification_list()

	def get_user_input(self):
		return input('user input: ')

	def quit(self):
		self.lock.acquire()
		self.state['listen'] = False
		self.lock.release()
		self.lock.acquire()
		self.state['done'] = True
		self.lock.release()

	def toggle_state(self, state):
		self.lock.acquire()
		self.state[state] = not self.state[state]
		self.lock.release()
	
	def get_convos(self):
		all_convos = redis_connection.keys('conversation_*')
		result = []
		for convo in all_convos:
			users = convo.split('_')[1:]
			if f'user{self.uid}' in users:
				result.append(convo)
		return result

	def get_notification_list(self):
		return self.redis_connection.lrange(f'notification_user{self.uid}',0,-1)


	# __ MULTITHREDED NOTIFICATION LISTENER __#
	def listen(self):
		update = False
		while self.state['listen']:
			time.sleep(1)
			self.lock.acquire()
			new_notification = self.get_notification_list()
			if self.notifications != new_notification:
				self.notifications = new_notification
				update = True
			self.lock.release()
			if update:	
				self.iterate(invalidate=True)
				update = False


if __name__ == '__main__':
	main()
