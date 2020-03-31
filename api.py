from flask import Flask, jsonify, request, render_template, send_from_directory
from datetime import datetime
import re
import os
import json
import mysql.connector

def load_config_file(filename="config.json"):
    with open(filename, 'r') as myfile:
        data=myfile.read()
    return json.loads(data)

def connect_db(db,schema=''):
    if schema == '':
        schema = str(config['databases'][db]['schema'])
    return mysql.connector.connect(
        host=str(config['databases'][db]['host']),
        user=str(config['databases'][db]['user']),
        database=schema,
        port=str(config['databases'][db]['port']),
        passwd=str(config['databases'][db]['password'])
    )

def get_current_timestamp():
	now = datetime.now()
	return datetime.strftime(now,'%Y%m%d_%H%M%S')

def get_text_id(db,text):
	query = ("SELECT `id` FROM `text` WHERE `text`=%s")
	args = [ text ]
	cursor = db.cursor()
	cursor.execute(query, args)
	for (id) in cursor:
		return id

	query = "INSERT IGNORE INTO `text` (`text`) VALUES (%s)"
	cursor = db.cursor()
	cursor.execute(query, args)
	return cursor.lastrowid

def get_container_id(db,image):
	query = "SELECT `id` FROM `container` WHERE `image`=%s"
	args = [ image ]
	cursor = db.cursor(buffered=True)
	cursor.execute(query, args)
	for (id) in cursor:
		return id

	query = "INSERT IGNORE INTO `container` (`image`) VALUES (%s)"
	args = [ image ]
	cursor = db.cursor(buffered=True)
	cursor.execute(query, args)
	return cursor.lastrowid

def get_executable_id(db,container_id,executable):
	cursor = db.cursor(buffered=True)
	if executable=="":
		query = "SELECT `id` FROM `executable` WHERE `container_id`=%s AND `name` IS NULL"
		cursor.execute(query, [container_id] )
	else:
		query = "SELECT `id` FROM `executable` WHERE `container_id`=%s AND `name`=%s"
		args = [container_id,executable]
		cursor.execute(query, args )
	for (id) in cursor:
		return id

	cursor = db.cursor(buffered=True)
	if executable=="":
		query = "INSERT IGNORE INTO `executable` (`container_id`) VALUES (%s)"
		cursor.execute(query, [container_id] )
	else:
		query = "INSERT IGNORE INTO `executable` (`container_id`,`name`) VALUES (%s,%s)"
		cursor.execute(query, [container_id,executable] )
	return cursor.lastrowid

def save_to_database(json):
	db = connect_db ( 'pathdb_rw' )
	container_id = get_container_id ( db , json["image"] )
	executable_id = get_executable_id ( db , container_id , json["executable"] )
	path_id = get_text_id ( db , json["path"] )
	parameters_id = get_text_id ( db , json["parameters"] )
	
	query = "INSERT IGNORE INTO `module_usage` (`user`,`timestamp`,`executable_id`,`path`,`parameters`) VALUES (%s,%s,%s,%s,%s)"
	args = (json["user"],json["timestamp"],executable_id,path_id,parameters_id)
	cursor = db.cursor()
	cursor.execute(query, args)
	cursor.close()

	return

def save_to_logfile(json):
	if not 'logfile' in config:
		return
	output = f'{json["user"]},{json["timestamp"]},{json["image"]},{json["path"]},{json["executable"]},{json["parameters"]}\n'
	with open(config["logfile"], "a") as logfile:
		logfile.write(output)
	return


app = Flask(__name__)
#app = Flask(__name__, static_url_path='') # If you want to serve static HTML pages
app.config["CACHE_TYPE"] = "null" # DEACTIVATES CACHE FOR DEVLEOPEMENT; COMMENT OUT FOR PRODUCTION!!!
app.config["DEBUG"] = True

config = load_config_file()

@app.route('/', methods=['GET'])
def home():
    return """
    <h1>Pathogens Software</h1>
    <p>This is an API to manange software installs by Pathogen Informatics.</p>
    Available API functions:
    <ul>
    	<li>
    		<p><b>query</b> [GET]</p>
    		<p>
    			Parameters:
	    		<ul>
	    			<li><tt>user</tt>=username (<i>optional</i>)</li>
	    			<li><tt>before</tt>=timestamp <= VALUE (<i>optional</i>)</li>
	    			<li><tt>after</tt>=timestamp >= VALUE (<i>optional</i>)</li>
	    			<li><tt>image</tt>=image name (<i>optional</i>)</li>
	    			<li><tt>executable</tt>=executable name (<i>optional</i>)</li>
	    			<li><tt>parameters</tt>=parameter string, finds all parameters with that substing (<i>optional</i>)</li>
	    		</ul>
	    	</p>
    	</li>
    </ul>
    """

@app.route('/query', methods=['GET'])
def query():
	ret = { "status":"OK" }
	user = request.args.get('user', default = '', type = str)
	before = request.args.get('before', default = '', type = str)
	after = request.args.get('after', default = '', type = str)
	image = request.args.get('image', default = '', type = str)
	executable = request.args.get('executable', default = '', type = str)
	parameters = request.args.get('parameters', default = '', type = str)
	db = connect_db('pathdb_ro')
	sql = [ '1=1' ]
	values = []
	if user!='':
		sql.append ( 'user=%s' )
		values.append ( user )
	if before!='':
		sql.append ( 'timestamp<=%s' )
		values.append ( before )
	if after!='':
		sql.append ( 'timestamp>=%s' )
		values.append ( after )
	if image!='':
		sql.append ( 'image=%s' )
		values.append ( image )
	if executable!='':
		sql.append ( 'executable=%s' )
		values.append ( executable )
	if parameters!='':
		sql.append ( 'parameters LIKE "%%%s%%"' )
		values.append ( parameters )
	sql = "SELECT * FROM vw_rows WHERE " +' AND '.join ( sql )
	mycursor = db.cursor(buffered=True)
	mycursor.execute(sql,values)
	ret['data'] = []
	for x in mycursor:
		ret['data'].append(x)
	return jsonify(ret)

@app.route('/log', methods=['GET','POST'])
def log():
	ret = { "status":"OK" }
	json = request.get_json()
	if 'executable' in json and 'image' in json and 'user' in json and 'path' in json:
		if not 'timestamp' in json:
			json["timestamp"] = get_current_timestamp()
		if not 'parameters' in json:
			json["parameters"] = ""
		else:
			json["parameters"] = json["parameters"].strip()
		json["executable"] = json["executable"].strip()
		json["image"] = json["image"].strip()
		json["user"] = json["user"].strip()
		json["path"] = json["path"].strip()
		save_to_database(json)
		save_to_logfile(json)
		ret["json"] = json
	else:
		ret["status"] = "ERROR: Missing JSON keys"

	return jsonify(ret)

if __name__ == "__main__":
	app.run()
