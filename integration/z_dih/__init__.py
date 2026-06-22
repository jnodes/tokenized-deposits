"""
IBM Z Data Integration Hub (DIH) Middleware Adapter
=====================================================
Provides the middleware bridge between the Issuing Bank's modern API platform
and the Hogan mainframe (CIF/DDA) on IBM Z.

Per the Issuing Bank's architecture: FastAPI -> IBM Z DIH (MQ/REST) -> Hogan COBOL/CICS
"""
from integration.z_dih.adapter import ZDIHAdapter, get_z_dih_adapter

__all__ = ["ZDIHAdapter", "get_z_dih_adapter"]
