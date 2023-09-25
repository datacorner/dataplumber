__author__ = "datacorner.fr"
__email__ = "admin@datacorner.fr"
__license__ = "MIT"

from pipelite.parents.DataSource import DataSource 
import utils.constants as C
from pipelite.etlDataset import etlDataset
from pyrfc import Connection, ABAPApplicationError, ABAPRuntimeError, LogonError, CommunicationError
from config.dpConfig import dpConfig as pc

# Parameters to have in the config file under /parameters
SAPPARAM_AHOST = "ahost"
SAPPARAM_CLIENT = "client"
SAPPARAM_SYSNR = "sysnr"
SAPPARAM_USER = "user"
SAPPARAM_PWD = "pwd"
SAPPARAM_ROUTER = "router"
SAPPARAM_TABLE = "table"
SAPPARAM_FIELDS = "fields"  # list of fields / column names
SAPPARAM_ROWCOUNT = "rowcount"

MANDATORY_PARAMETERS = [SAPPARAM_AHOST, 
                        SAPPARAM_CLIENT, 
                        SAPPARAM_SYSNR, 
                        SAPPARAM_USER, 
                        SAPPARAM_PWD, 
                        SAPPARAM_TABLE]

class sapRfcTableDS(DataSource):
    def __init__(self, config, log):
        super().__init__(config, log)
        self.ahost = C.EMPTY
        self.client = C.EMPTY
        self.sysnr = C.EMPTY
        self.user = C.EMPTY
        self.pwd = C.EMPTY
        self.router = C.EMPTY
        self.table = C.EMPTY
        self.fields = []
        self.rowcount = 0

    def initialize(self, params) -> bool:
        """ initialize and check all the needed configuration parameters
        Args:
            params (json list) : params for the data source.
        Returns:
            bool: False if error
        """
        try:
            # checks
            for param in MANDATORY_PARAMETERS:
                if (self.getValFromDict(params, param, C.EMPTY)):
                    raise Exception("Mandatory Parameter <{}> is missing".format(param))
            # Get params
            self.ahost = self.getValFromDict(params, SAPPARAM_AHOST, C.EMPTY)
            self.client = self.getValFromDict(params, SAPPARAM_CLIENT, C.EMPTY)
            self.sysnr = self.getValFromDict(params, SAPPARAM_SYSNR, C.EMPTY)
            self.user = self.getValFromDict(params, SAPPARAM_USER, C.EMPTY)
            self.pwd = self.getValFromDict(params, SAPPARAM_PWD, C.EMPTY)
            self.router = self.getValFromDict(params, SAPPARAM_ROUTER, C.EMPTY)
            self.table = self.getValFromDict(params, SAPPARAM_TABLE, C.EMPTY)
            self.fields = self.getValFromDict(params, SAPPARAM_FIELDS, [])
            self.rowcount = self.getValFromDict(params, SAPPARAM_ROWCOUNT, 0)
            return True
        except Exception as e:
            self.log.error("CSVFileDS.initialize() Error: {}".format(e))
            return False

    def __connectToSAP__(self) -> Connection:
        """ Connect to the SAP instance via RFC
        Returns:
            connection: SAP Connection
        """
        try:
            # Get the SAP parmaters first
            self.log.info("Connect to SAP via RFC")
            conn = Connection(ashost=self.ahost, 
                              sysnr=self.sysnr, 
                              client=self.client, 
                              user=self.user, 
                              passwd=self.pwd, 
                              saprouter=self.router)
            return conn
        except CommunicationError:
            self.log.error("sapRfcDS.__connectToSAP() Could not connect to server.")
        except LogonError:
            self.log.error("sapRfcDS.__connectToSAP() Could not log in. Wrong credentials?")
            print("Could not log in. Wrong credentials?")
        except (ABAPApplicationError, ABAPRuntimeError):
            self.log.error("sapRfcDS.__connectToSAP(): An error occurred")
        return None

    def __callRFCReadTable__(self, conn) -> etlDataset:
        """ Call the RFC_READ_TABLE BAPI and get the dataset as result
        Args:
            conn (_type_): SAP Connection via pyrfc
        Returns:
            etlDataset: dataset 
        """
        try:
            # Get the list of fields to gather
            # Call RFC_READ_TABLE
            self.log.info("Gather data from the SAP Table")
            result = conn.call("RFC_READ_TABLE",
                                ROWCOUNT=self.rowcount,
                                QUERY_TABLE=self.table,
                                FIELDS=self.fields)

            # Get the data & create the dataFrame
            data = result["DATA"]
            self.log.info("<{}> rows has been read from SAP".format(len(data)))
            fields = result["FIELDS"]

            records = []
            for entry in data:
                record = {}
                for i, field in enumerate(fields):
                    field_name = field["FIELDNAME"]
                    idx = int(field["OFFSET"])
                    length = int(field["LENGTH"])
                    field_value = str(entry["WA"][idx:idx+length])
                    record[field_name] = field_value
                records.append(record)
            res = etlDataset()
            res.initFromList(records, defaultype=str)
            return res

        except Exception as e:
            self.log.error("sapRfcDS.__callRFCReadTable__() Exception -> " + str(e))
            return etlDataset()

    def extract(self) -> int:
        """ flaten the XES (XML format) and returns all the data in a etlDataset format
        Returns:
            etlDataset: data set
        """
        try:
            sapConn = self.__connectToSAP__()
            if (sapConn != None):
                self.content = self.__callRFCReadTable(sapConn)
            return self.content.count
        except Exception as e:
            self.log.error("sapRfcDS.extract() Error while accessing the SAP RFC Table: ".format(e))
            return False