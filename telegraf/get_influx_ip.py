import flask_restful as restful
from flask import jsonify, make_response
from flask import request
from configs.readconfig import configp
import pymysql as MySQLdb
from netaddr import valid_ipv4


def influx_db_info(vm_type):
    user = configp.get(vm_type, 'username')
    pas = configp.get(vm_type, 'password')
    host = configp.get(vm_type, 'host')
    db_influx = configp.get(vm_type, 'database')
    conn = MySQLdb.connect(host=host, user=user, passwd=pas, db=db_influx)
    c = conn.cursor()
    return c, conn


class InfluxIP(restful.Resource):

    def get(self):
        influx_ip = None
        secondary_influx_node = None
        try:
            self.data = request.get_json()
            self.serverip = self.data['serverip']
            self.vm_type = self.data.get("vm_template", None).lower()

            cur, con = influx_db_info(self.vm_type)

            if self.vm_type not in ['application','database']:
                return "Invalid VM template", 400

            self.table_influx = configp.get(self.vm_type, 'tablename')


            query="select influx_node,secondary_influx_node from %s where ip='%s'" %(self.table_influx,self.serverip)

            val = valid_ipv4(self.serverip)

            if val == True:
                pass
            else:
                print "Invalid IP address %s" % (self.serverip)
                return "Invalid IP address", 400

            cur.execute(query)

            rows = cur.fetchall()
            for row in rows:
                influx_ip = row[0]
                secondary_influx_node = row[1]
                break

        except Exception as e:
            print e

        finally:
            cur.close()
            con.close()
        return make_response(jsonify({"influx_ip": influx_ip,"secondary_influx_node": secondary_influx_node}))

