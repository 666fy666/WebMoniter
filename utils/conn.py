# connect_db：连接数据库，并操作数据库
import pymysql

class OperationMysql:
    """
    数据库操作类 (优化版)
    支持上下文管理器，支持断连重连，合并冗余代码
    """

    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cur = None
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = pymysql.connect(
                host=self.config["dbs"]["host"],
                port=self.config["dbs"].get("port", 3306), # 兼容配置中没有port的情况，默认3306
                user=self.config["dbs"]["user"],
                passwd=self.config["dbs"]["password"],
                db=self.config["dbs"]["db"],
                charset='utf8mb4', # 推荐明确指定字符集
                cursorclass=pymysql.cursors.Cursor # 默认返回元组，如需返回字典可改为 DictCursor
            )
            self.cur = self.conn.cursor()
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise e

    def _ensure_connection(self):
        """确保连接可用，如果断开则重连 (用于长脚本监控)"""
        if not self.conn or not self.conn.open:
            self.connect()
        else:
            try:
                # ping一下，如果断开则自动重连
                self.conn.ping(reconnect=True)
                # ping 重连后需要重新获取游标
                self.cur = self.conn.cursor()
            except:
                self.connect()

    def search_one(self, sql, data=None):
        """
        查询数据
        优化：增加了 data 参数，支持参数化查询，防止 SQL 注入
        """
        self._ensure_connection()
        try:
            self.cur.execute(sql, data)
            # 虽然方法名叫 search_one，但原逻辑是 fetchall，这里保持原逻辑不变
            result = self.cur.fetchall() 
            return result
        except Exception as e:
            print(f"查询出错: {e} \nSQL: {sql}")
            return () # 出错返回空元组，防止后续代码报错

    def execute_cud(self, sql, data):
        """
        统一处理 Create, Update, Delete 操作
        优化：合并了 insert/update/delete 的重复逻辑
        注意：移除了 close()，支持单次连接多次操作
        """
        self._ensure_connection()
        try:
            self.cur.execute(sql, data)
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"执行出错: {e}")
            return False

    # 保持原有的方法名接口，兼容旧代码调用，但底层调用统一的方法
    def updata_one(self, sql, data):
        return self.execute_cud(sql, data)

    def insert_one(self, sql, data):
        return self.execute_cud(sql, data)

    def delete_one(self, sql, data):
        return self.execute_cud(sql, data)

    def close(self):
        """显式关闭连接"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """支持 with OperationMysql(config) as db: 语法"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 语句时自动关闭连接"""
        self.close()

    def __del__(self):
        """析构函数，对象销毁时尝试关闭连接"""
        self.close()

'''
if __name__ == '__main__':
    op_mysql = OperationMysql(config)
    res = op_mysql.search_one("SELECT *  from odi_order WHERE order_no='12222'")
    print(res)
'''