from __future__ import annotations
import os
from typing import Dict, Any, Optional
from zeep import Client
from zeep.transports import Transport
from zeep.helpers import serialize_object
import requests

TOKEN = os.getenv("NRE_LDBWS_TOKEN")
WSDL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

class OpenLDBWS:
    def __init__(self) -> None:
        session = requests.Session()
        session.headers.update({"X-Access-Token": TOKEN})
        self.client = Client(WSDL, transport=Transport(session=session))

    def live_departures(
        self,
        crs: str,
        destination: Optional[str] = None,
        when: Optional[str] = None,  # Darwin doesn’t support 'when' the same way; ignored here
        limit: int = 5,
    ) -> Dict[str, Any]:
        svc = self.client.service
        if destination:
            resp = svc.GetDepBoardWithDetails(numRows=limit, crs=crs, filterCrs=destination, filterType="to")
        else:
            resp = svc.GetDepartureBoard(numRows=limit, crs=crs)
        return serialize_object(resp)
