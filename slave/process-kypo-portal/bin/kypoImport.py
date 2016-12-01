#!/usr/bin/python
'''
This script imports users and groups from json to KYPO AAI database.
JSON files were generated by perun-service named kypo_portal.

author:  Frantisek Hrdina
date:    2016-05-02 
version: 1.0.0

2016-05-13: In getting data from DB added code to ignore testing DB entries with no external_id
2016-11-17: Correct typo in code, parrent -> parent
2016-11-30: Fixed errors with parent groups, error messages
2016-12-01: Subgroups are stored in DB without prefix of parent group
'''

import sys
import json
import psycopg2

'''Information to access DB'''
DB_NAME = 'SET DB NAME HERE'
DB_USER = 'SET DB USER HERE'
DB_HOST = 'SET DB HOST HERE'
DB_PSSWD = 'SET PASSWORD HERE'

CONN_STRING = "dbname='{0}' user='{1}' host='{2}' password='{3}'".format(DB_NAME, DB_USER, DB_HOST, DB_PSSWD)

''' Names of tables in DB'''
USER_TABLE = 'users'
GROUP_TABLE = 'idm_group'
IDENTITY_TABLE = 'user_identity'
USERINGROUP_TABLE = 'user_idm_group'

''' Source JSON files '''
USERS_SRC = '/tmp/users.scim'
GROUPS_SRC = '/tmp/groups.scim'

try:
	conn = psycopg2.connect(CONN_STRING)
except:
	print "Unable to connect to DB"
	sys.exit(1)

''' DEFINING VARIABLES '''
class User(object):
	def __init__(self):
		self.displayName = ""
		self.mail = ""
		self.status = ""
		self.external_id = 0

	def __eq__(self,other):
		return self.displayName == other.displayName and self.mail == other.mail and self.status == other.status and self.external_id == other.external_id  

class Group(object):
	def __init__(self):
		self.name = ""
		self.external_id = 0
		self.parent_group_id = 0

	def __eq__(self,other):
		return self.name == other.name and self.external_id == other.external_id

class Identity(object):
	def __init__(self):
		self.user_id = 0
		self.external_id = 0
		self.login = ""
		
	def __eq__(self,other):
		return self.external_id == other.external_id and self.login == other.login

class UserInGroup(object):
	def __init__(self):
		self.group_id = 0
		self.user_id = 0
		self.group_external_id = 0
		self.user_external_id = 0

	def __eq__(self,other):
		return self.group_external_id == other.group_external_id and self.user_external_id == other.user_external_id

usersDB = list()
groupsDB = list()
identitiesDB = list()
userInGroupDB = list()

userDB_ids = list() 
userIdsToUpd = list()
userIdsToDis = list()

groupDB_ids = list()
groupIdsToUpd = list()
groupIdsToDel = list()

userJSON_ids = list()
groupJSON_ids = list()
identities_json = list()

users_list = list()
identities_list = list()
groups_list = list()
usersInGroups_list = list()

changedUsers = list()
changesGroups = list()
identitiesToDel = list()

''' GETTING DATA FROM JSON '''
json_users = open(USERS_SRC)
users_data = json.load(json_users)
json_users.close()

json_groups = open(GROUPS_SRC)
groups_data = json.load(json_groups)
json_groups.close()

''' PARSING DATA FROM users.scim '''
for item in users_data:
	userJSON_ids.append(int(item['id']))	
	tmpUser = User()
	tmpUser.displayName = (item['displayName']).encode('utf-8')
	tmpUser.mail = (item['mail']).encode('utf-8')
	tmpUser.status = (item['status']).encode('utf-8')
	tmpUser.external_id = int(item['id'])
	users_list.append(tmpUser)

	for i in item['identities']:
		identities_json.append(i.encode('utf-8'))
		tmpIdentity = Identity()
		tmpIdentity.login = i.encode('utf-8')
		tmpIdentity.external_id = int(item['id'])
		identities_list.append(tmpIdentity)

''' PARSING DATA FROM groups.scim '''		
for item in groups_data:
	groupJSON_ids.append(int(item['id']))
	tmpGroup = Group()
	tmpGroup.name = (item['name']).encode('utf-8')
	tmpGroup.external_id = int(item['id'])
	
	if item['parentGroupId'] is None:
		tmpGroup.parent_group_id = None
	else:
		tmpGroup.parent_group_id = int(item['parentGroupId'])
		#This removes prefix of parent group exported from perun, that is not suitable
		tmpGroup.name = tmpGroup.name.split(':')[-1]


	groups_list.append(tmpGroup)
	
	for i in item['members']:
		tmpUserInGroup = UserInGroup()
		tmpUserInGroup.user_external_id = int(i['userId'])
		tmpUserInGroup.group_external_id = int(item['id'])
		usersInGroups_list.append(tmpUserInGroup)

''' WORK WITH DB '''
cur = conn.cursor()

''' GETTING ACTUAL USERS FROM DB '''
try:
	cur.execute('SELECT * FROM {0};'
		.format(USER_TABLE));
except psycopg2.Error as e:
	print('Getting users: DB Error {0}').format(e)
	cur.close()
	conn.close()
	sys.exit(1)

for row in cur:
	#This prevent to manipulation with testing data in db with no ext id
	if row[2] is None:
		continue

	userDB_ids.append(row[2])
	tmpUser = User()
	tmpUser.displayName = row[1]
	tmpUser.mail = row[3]
	tmpUser.status = row[4]
	tmpUser.external_id = row[2]
	usersDB.append(tmpUser)

''' GETTING USERS THAT HAVE BEEN CHANGED TO LIST '''	
changedUsers = [item for item in users_list if item not in usersDB]

for item in changedUsers:
	userIdsToUpd.append(item.external_id)

''' GETTING USERS THAT ARE NOT IN JSON BUT IN DB TO LIST '''
userIdsToDis = list(set(userDB_ids) - set(userJSON_ids))

''' INSERTS AND UPDATES OF USERS '''
for item in users_list:	
	if int(item.external_id) not in userDB_ids:
		try:
			cur.execute('INSERT INTO {0} (id, display_name, mail, status, external_id) VALUES (default, '"'{1}'"', '"'{2}'"', '"'{3}'"', '"'{4}'"');'
				.format(USER_TABLE, item.displayName, item.mail, item.status, item.external_id))
		except psycopg2.Error as e:
			print('Inserting user with ext_id:{0} DB Error {1}').format(item.external_id, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

	if int(item.external_id) in userIdsToUpd:	
		try:
			cur.execute('UPDATE {0} SET display_name = '"'{1}'"', mail = '"'{2}'"', status = '"'{3}'"' WHERE external_id = '"'{4}'"';'
				.format(USER_TABLE, item.displayName, item.mail, item.status, item.external_id))
		except psycopg2.Error as e:
			print('Updating user with ext_id:{0} DB Error {1}').format(item.external_id, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

''' GETTING ACTUAL GROUPS FROM DB '''
try:
	cur.execute('SELECT * FROM {0};'
		.format(GROUP_TABLE))
except psycopg2.Error as e:
	print('Getting groups: DB Error {0}').format(e)
	cur.close()
	conn.close()
	sys.exit(1)

for row in cur:
	#This prevent to manipulation with testing data in db with no ext id
	if row[1] is None:
		continue
	
	groupDB_ids.append(row[1])
	tmpGroup = Group()
	tmpGroup.name = row[2]
	tmpGroup.external_id = row[1]
	tmpGroup.parent_group_id = row[3]
	groupsDB.append(tmpGroup)

''' GETTING GROUPS THAT HAVE BEEN CHANGED TO LIST'''
changedGroups = [item for item in groups_list if item not in groupsDB]

for item in changedGroups:
	groupIdsToUpd.append(item.external_id)

''' GETTING GROUPS THAT ARE NOT IN JSON BUT IN DB TO LIST '''
groupIdsToDel = list(set(groupDB_ids) - set(groupJSON_ids))

''' INSERTS AND UPDATES OF GROUPS '''
for item in groups_list:	
	if int(item.external_id) not in groupDB_ids:
		try:
			if item.parent_group_id is not None:
				cur.execute('SELECT id FROM {0} WHERE external_id = '"'{1}'"';'
					.format(GROUP_TABLE, item.parent_group_id))
                        	id = cur.fetchone()[0]

				cur.execute('INSERT INTO {0} (id, name, external_id, parent_group_id) VALUES (default, '"'{1}'"', '"'{2}'"', {3});'
					.format(GROUP_TABLE, item.name, item.external_id, id))
			else:
				cur.execute('INSERT INTO {0} (id, name, external_id) VALUES (default, '"'{1}'"', '"'{2}'"');'
					.format(GROUP_TABLE, item.name, item.external_id))

		except psycopg2.Error as e:
			print('Inserting group with ext_id:{0} DB Error {1}').format(item.external_id, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

	if int(item.external_id) in groupIdsToUpd:	
		try:
			
			if item.parent_group_id is not None:
				cur.execute('SELECT id FROM {0} WHERE external_id = '"'{1}'"';'
					.format(GROUP_TABLE, item.parent_group_id))
                       		id = cur.fetchone()[0]
		
				cur.execute('UPDATE {0} SET name = '"'{1}'"', parent_group_id = {2}  WHERE external_id = '"'{3}'"';'
					.format(GROUP_TABLE, item.name, id, item.external_id))
			else:
				cur.execute('UPDATE {0} SET name = '"'{1}'"'  WHERE external_id = '"'{2}'"';'
					.format(GROUP_TABLE, item.name, item.external_id))
		except psycopg2.Error as e:
			print('Updating group with ext_id:{0} DB Error {1}').format(item.external_id, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

''' GETTING ACTUAL IDENTITES FROM DB '''
try:
	cur.execute('SELECT id, external_id, login FROM {0}, {1} WHERE id = user_id;'
		.format(USER_TABLE, IDENTITY_TABLE))
except psycopg2.Error as e:
	print('Getting identities: DB Error {0}').format(e)
	cur.close()
	conn.close()
	sys.exit(1)

for row in cur:
	tmpIdentity = Identity()
	tmpIdentity.login = row[2]
	tmpIdentity.external_id = row[1]
	tmpIdentity.user_id = row[0]
	identitiesDB.append(row[2])

''' GETTING IDENTITIES NOT IN JSON BUT IN DB '''
identitiesToDel = list(set(identitiesDB) - set(identities_json))

''' INSERTS OF IDENTITIES '''
for item in identities_list:
	if item.login not in identitiesDB:
		try:
			cur.execute('SELECT id FROM {0} WHERE external_id = {1};'
				.format(USER_TABLE, item.external_id))
			id = cur.fetchone()[0]
			cur.execute('INSERT INTO {0} (user_id, login) VALUES ('"'{1}'"', '"'{2}'"');'
				.format(IDENTITY_TABLE, id, item.login))
		except psycopg2.Error as e:
			print('Inserting identity with_login:{0} DB Error {1}')	.format(item.login, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

''' GETTING ACTUAL MEMBERSHIPS FROM DB '''
try:
	cur.execute('SELECT {1}.id, {0}.id, {1}.external_id, {0}.external_id FROM {0}, {1}, {2} WHERE {0}.id = {2}.user_id and {1}.id = {2}.idm_group_id;'
		.format(USER_TABLE, GROUP_TABLE, USERINGROUP_TABLE))
except psycopg2.Error as e:
	print('Getting memberships: DB Error {0}').format(e)
	cur.close()
	conn.close()
	sys.exit(1)

for row in cur:
	#This prevent to manipulation with testing data in db with no ext id
	if row[2] is None or row[3] is None:
		continue
	
	tmpUserInGroup = UserInGroup()
	tmpUserInGroup.group_id = int(row[0])
	tmpUserInGroup.user_id = int(row[1])
	tmpUserInGroup.group_external_id = int(row[2])
	tmpUserInGroup.user_external_id = int(row[3])
	userInGroupDB.append(tmpUserInGroup)

''' INSERTS NEW MEMBERSHIPS FROM JSON '''
for item in usersInGroups_list:
	if item not in userInGroupDB:
		try:
			cur.execute('SELECT id FROM {0} WHERE external_id = {1};'
				.format(USER_TABLE, item.user_external_id))
			user_id = cur.fetchone()[0]
			cur.execute('SELECT id FROM {0} WHERE external_id = {1};'
				.format(GROUP_TABLE, item.group_external_id))
			group_id = cur.fetchone()[0]
			cur.execute('INSERT INTO {0} (user_id, idm_group_id) VALUES('"'{1}'"', '"'{2}'"');'
				.format(USERINGROUP_TABLE, user_id, group_id))
		except psycopg2.Error as e:
			print('Inserting membership with user.ext_id:{0} and group.ext_id:{1} DB Error {2}').format(item.user_external_id, item.group_external_id, e)
			cur.close()
			conn.close()
			sys.exit(1)
		conn.commit()

''' MEMBERSHIPS NOT IN JSON WILL BE DELETED '''
userInGroupToDel = [item for item in userInGroupDB if item not in usersInGroups_list]

''' DELETING MEMBERSHIPS FROM DB '''
for item in userInGroupToDel:
	try:
		cur.execute('DELETE FROM {0} WHERE user_id = '"'{1}'"' and idm_group_id = '"'{2}'"';'
			.format(USERINGROUP_TABLE, item.user_id, item.group_id))
	except psycopg2.Error as e:
		print('Deleting membership with user.id:{0} and group._id:{1} DB Error {0}').format(item.user_id, item.group_id, e)
		cur.close()
		conn.close()
		sys.exit(1)
	conn.commit()

''' DELETING IDENTITIES FROM DB '''
for item in identitiesToDel:
	try:
		cur.execute('DELETE FROM {0} WHERE login = '"'{1}'"';'
			.format(IDENTITY_TABLE, item))
	except psycopg2.Error as e:
		print('Deleting identity with login:{0} DB Error {1}').format(item, e)
		cur.close()
		conn.close()
		sys.exit(1)
	conn.commit()

''' USERS NOT IN JSON ARE SETTED TO DISABLE'''
for item in userIdsToDis:
	try:
		cur.execute ('UPDATE {0} SET status  = '"'disabled'"' WHERE external_id = '"'{1}'"';'
			.format(USER_TABLE, item))
	except psycopg2.Error as e:
		print('Disabling users: DB Error {0}').format(e)
		cur.close()
		conn.close()
		sys.exit(1)
	conn.commit()

''' FROM GROUPS NOT IN JSON ARE DELETED ALL USERS ''' 
for item in groupIdsToDel:
	try:
		cur.execute('SELECT id FROM {0} WHERE external_id = '"'{1}'"';'
			.format(GROUP_TABLE, item))
		group_id = cur.fetchone()[0]
		cur.execute('DELETE FROM {0} WHERE group_id = '"'{1}'"';'
			.format(USERINGROUP_TABLE, group_id))
	except psycopg2.Error as e:
		print('Deleting users from group: DB Error {0}').format(e)
		cur.close()
		conn.close()
		sys.exit(1)
	conn.commit()

cur.close()
conn.close()
