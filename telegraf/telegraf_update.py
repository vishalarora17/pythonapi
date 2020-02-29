import flask_restful as restful
from flask import jsonify, make_response
from flask import request
from configs.readconfig import configp
from models.models import db, Access_Info, DB_USER_INFO
import requests
import json
import string
import random
import paramiko
from auth.authentication import valid_token,common_validator
import base64
import pymysql as MySQLdb
import datetime
from netaddr import valid_ipv4


class Telegraf(restful.Resource):

    def post(self):

        try:

            self.data = request.get_json()
            self.serverip = self.data['serverip']
            self.vm_type = self.data.get("vm_type", None)

            val = valid_ipv4(self.serverip)

            if val == True:
                pass
            else:
                print "Invalid IP address %s" % (self.serverip)
                return "Invalid IP address", 400

            response = self.updateconfig()
            #MySQL query to insert get information
            def mysql_connection():
                user = configp.get('mysql', 'username')
                pas = base64.b64decode(configp.get('mysql', 'password'))
                host = configp.get('mysql', 'host')
                db_pcli = configp.get('mysql', 'database')

                mysql_conn = MySQLdb.connect(host=host,
                                             user=user,
                                             passwd=pas,
                                             db=db_pcli)
                return mysql_conn

            insert_sql = 'insert into telegraf_info(created_date,server_ip,message,status_code, vm_type) values (%s,%s,%s,%s,%s)'
            mysql_conn = mysql_connection()
            mysql_cursor = mysql_conn.cursor()

            if response[0]:
                run_date = datetime.datetime.now()
                values = [run_date, self.serverip, response[1], response[2], self.vm_type.upper()]
                mysql_cursor.execute(insert_sql, values)
                mysql_conn.commit()
                return make_response(jsonify({"status": 1, "message": response[1], "status_code": response[2]}))
            else:
                run_date = datetime.datetime.now()
                values = [run_date, self.serverip, response[1], response[2], self.vm_type.upper()]
                mysql_cursor.execute(insert_sql, values)
                mysql_conn.commit()
                return make_response(jsonify({"status": 0, "message": response[1], "status_code": response[2]}))
        except Exception as e:
            print e

    def agent_auth(self, transport, username):

        try:
            ki = paramiko.RSAKey.from_private_key_file(self.rsa_private_key)
        except Exception, e:
            print 'Failed loading' % (self.rsa_private_key, e)

        agent = paramiko.Agent()
        agent_keys = agent.get_keys() + (ki,)

        if len(agent_keys) == 0:
            return

        for key in agent_keys:
            print 'Trying ssh-agent key %s' % key.get_fingerprint().encode('hex'),
            try:
                transport.auth_publickey(username, key)
                print '... success!'
                return
            except paramiko.SSHException, e:
                print '... failed!', e

    def updateconfig(self):

        try:
            if self.vm_type == "application":

                ### ANSIBLE PATHS
                ansible_base_path = configp.get('application-ansibleconfig', 'path')

                ### CONFIGS
                hostname = configp.get('application-ansibleconfig', 'hostname')
                port = int(configp.get('application-ansibleconfig', 'port'))
                username = configp.get('application-ansibleconfig', 'username')
                self.rsa_private_key = configp.get('application-ansibleconfig', 'rsakey')

                ###COMMANDS
                ansible_command = 'sudo ansible-playbook -i %s, playbooks/telegraf.yml -e "nginx_plus_enabled_required=False" -e "nginx_plus_enabled_required_auth=False"' % (
                self.serverip)
                command = "cd " + ansible_base_path + " && " + ansible_command

            elif self.vm_type == "database":
                ### ANSIBLE PATHS
                ansible_base_path = configp.get('database-ansibleconfig', 'path')

                ### CONFIGS
                hostname = configp.get('database-ansibleconfig', 'hostname')
                port = int(configp.get('database-ansibleconfig', 'port'))
                username = configp.get('database-ansibleconfig', 'username')
                self.rsa_private_key = configp.get('database-ansibleconfig', 'rsakey')

                ###COMMANDS
                ansible_command = 'ansible-playbook -i %s, /etc/ansible/ -e "rtpasswd=%s"' % (
                self.serverip, rpassword)
                command = "cd " + ansible_base_path + " && " + ansible_command

            else:
                return False, "VM type incorrect", 400

            ### SETTING PASSWORD ON SERVER
            print 'Establishing SSH connection to:', hostname, port, '...'
            t = None
            exitstatus = -1
            try:
                t = paramiko.Transport((hostname, port))
                t.start_client()
                self.agent_auth(t, username)

                if not t.is_authenticated():
                    print 'RSA key auth failed! Trying password login...'
                else:

                    ssh = paramiko.SSHClient()

                    try:
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        ssh.connect(hostname=hostname, username=username, key_filename=self.rsa_private_key)
                        chan = ssh.get_transport().open_session()

                        chan.exec_command(command)

                        exitstatus = chan.recv_exit_status()


                    finally:
                        ssh.close()
            finally:
                if t:
                    t.close()

            if exitstatus == 0:
                return True, "Telegraf Config Updated Successfully", 200
            else:
                requests.request('DELETE', msecreturl, headers=headers)
                return False, "Telegraf Config Updation Failed", 400

        except Exception as e:
            print e

