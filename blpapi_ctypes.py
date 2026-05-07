"""
Minimal Bloomberg Desktop API client using ctypes against blpapi3_64.dll.
Implements synchronous BDP (reference data) only — enough for price, YTW, multiples.

No compilation required. Uses the DLL already installed by Bloomberg Anywhere.
Requires Bloomberg Anywhere to be running and authenticated (port 8194 open).
"""

import ctypes
import time
from ctypes import c_void_p, c_char_p, c_int, c_uint, c_double, c_ulong, POINTER

DLL_PATH = r"C:\blp\DAPI\blpapi3_64.dll"

# Event types (from blpapi_event.h)
BLPAPI_EVENTTYPE_ADMIN               = 1
BLPAPI_EVENTTYPE_SESSION_STATUS      = 2
BLPAPI_EVENTTYPE_SUBSCRIPTION_STATUS = 3
BLPAPI_EVENTTYPE_REQUEST_STATUS      = 4
BLPAPI_EVENTTYPE_RESPONSE            = 5
BLPAPI_EVENTTYPE_PARTIAL_RESPONSE    = 6
BLPAPI_EVENTTYPE_SERVICE_STATUS      = 8
BLPAPI_EVENTTYPE_TIMEOUT             = 9
BLPAPI_EVENTTYPE_REQUEST             = 14

# Data types
BLPAPI_DATATYPE_FLOAT64 = 9
BLPAPI_DATATYPE_STRING  = 11


def _load():
    lib = ctypes.CDLL(DLL_PATH)

    # Session options
    lib.blpapi_SessionOptions_create.restype  = c_void_p
    lib.blpapi_SessionOptions_destroy.argtypes = [c_void_p]
    lib.blpapi_SessionOptions_setServerHost.argtypes = [c_void_p, c_char_p, c_uint]
    lib.blpapi_SessionOptions_setServerPort.argtypes = [c_void_p, c_uint]

    # Session
    lib.blpapi_Session_create.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p]
    lib.blpapi_Session_create.restype   = c_void_p
    lib.blpapi_Session_destroy.argtypes = [c_void_p]
    lib.blpapi_Session_start.argtypes   = [c_void_p]
    lib.blpapi_Session_start.restype    = c_int
    lib.blpapi_Session_stop.argtypes    = [c_void_p]
    lib.blpapi_Session_openService.argtypes = [c_void_p, c_char_p]
    lib.blpapi_Session_openService.restype  = c_int
    lib.blpapi_Session_getService.argtypes  = [c_void_p, POINTER(c_void_p), c_char_p]
    lib.blpapi_Session_getService.restype   = c_int
    lib.blpapi_Session_sendRequest.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_char_p, c_int]
    lib.blpapi_Session_sendRequest.restype  = c_int
    lib.blpapi_Session_nextEvent.argtypes   = [c_void_p, POINTER(c_void_p), c_uint]
    lib.blpapi_Session_nextEvent.restype    = c_int

    # Service / Request
    lib.blpapi_Service_createRequest.argtypes = [c_void_p, POINTER(c_void_p), c_char_p]
    lib.blpapi_Service_createRequest.restype  = c_int
    lib.blpapi_Request_elements.argtypes = [c_void_p]
    lib.blpapi_Request_elements.restype  = c_void_p
    lib.blpapi_Request_destroy.argtypes  = [c_void_p]

    # Element
    lib.blpapi_Element_getElement.argtypes    = [c_void_p, POINTER(c_void_p), c_char_p, c_void_p]
    lib.blpapi_Element_getElement.restype     = c_int
    lib.blpapi_Element_setValueString.argtypes= [c_void_p, c_char_p, c_uint]
    lib.blpapi_Element_setValueString.restype = c_int
    lib.blpapi_Element_appendElement.argtypes = [c_void_p, POINTER(c_void_p)]
    lib.blpapi_Element_appendElement.restype  = c_int
    lib.blpapi_Element_setElementString.argtypes = [c_void_p, c_char_p, c_void_p, c_char_p]
    lib.blpapi_Element_setElementString.restype  = c_int
    lib.blpapi_Element_numValues.argtypes   = [c_void_p]
    lib.blpapi_Element_numValues.restype    = c_ulong
    lib.blpapi_Element_numElements.argtypes = [c_void_p]
    lib.blpapi_Element_numElements.restype  = c_ulong
    lib.blpapi_Element_getValueAsFloat64.argtypes = [c_void_p, POINTER(c_double), c_uint]
    lib.blpapi_Element_getValueAsFloat64.restype  = c_int
    lib.blpapi_Element_getValueAsString.argtypes  = [c_void_p, POINTER(c_char_p), c_uint]
    lib.blpapi_Element_getValueAsString.restype   = c_int
    lib.blpapi_Element_getElementAt.argtypes = [c_void_p, POINTER(c_void_p), c_uint]
    lib.blpapi_Element_getElementAt.restype  = c_int
    lib.blpapi_Element_nameString.argtypes   = [c_void_p]
    lib.blpapi_Element_nameString.restype    = c_char_p

    # Event / Message
    lib.blpapi_Event_eventType.argtypes         = [c_void_p]
    lib.blpapi_Event_eventType.restype          = c_int
    lib.blpapi_MessageIterator_create.argtypes  = [c_void_p]
    lib.blpapi_MessageIterator_create.restype   = c_void_p
    lib.blpapi_MessageIterator_destroy.argtypes = [c_void_p]
    lib.blpapi_MessageIterator_next.argtypes    = [c_void_p, POINTER(c_void_p)]
    lib.blpapi_MessageIterator_next.restype     = c_int
    lib.blpapi_Message_elements.argtypes        = [c_void_p]
    lib.blpapi_Message_elements.restype         = c_void_p

    return lib


def _read_element(lib, elem) -> dict | str | float | None:
    """Recursively read a blpapi Element into a Python value."""
    n_vals = lib.blpapi_Element_numValues(elem)
    n_elems = lib.blpapi_Element_numElements(elem)

    if n_elems > 0:
        # Struct — recurse into sub-elements
        out = {}
        for i in range(n_elems):
            child = c_void_p()
            if lib.blpapi_Element_getElementAt(elem, ctypes.byref(child), i) == 0:
                name = lib.blpapi_Element_nameString(child)
                if name:
                    out[name.decode()] = _read_element(lib, child)
        return out

    if n_vals == 0:
        return None

    if n_vals > 1:
        # Array
        out = []
        for i in range(n_vals):
            val = c_double()
            sval = c_char_p()
            if lib.blpapi_Element_getValueAsFloat64(elem, ctypes.byref(val), i) == 0:
                out.append(val.value)
            elif lib.blpapi_Element_getValueAsString(elem, ctypes.byref(sval), i) == 0 and sval.value:
                out.append(sval.value.decode())
        return out

    # Scalar — try float first, then string
    val = c_double()
    if lib.blpapi_Element_getValueAsFloat64(elem, ctypes.byref(val), 0) == 0:
        return val.value
    sval = c_char_p()
    if lib.blpapi_Element_getValueAsString(elem, ctypes.byref(sval), 0) == 0 and sval.value:
        return sval.value.decode()
    return None


def bdp(securities: list[str], fields: list[str],
        host: str = "localhost", port: int = 8194,
        timeout_ms: int = 20_000) -> dict:
    """
    Synchronous BDP-equivalent reference data fetch.
    Returns {security: {field: value}}.
    Raises RuntimeError if Bloomberg is unavailable.
    """
    lib = _load()

    # Create session
    opts = lib.blpapi_SessionOptions_create()
    lib.blpapi_SessionOptions_setServerHost(opts, host.encode(), 0)
    lib.blpapi_SessionOptions_setServerPort(opts, port)
    session = lib.blpapi_Session_create(opts, None, None, None)

    if lib.blpapi_Session_start(session) != 0:
        lib.blpapi_Session_destroy(session)
        raise RuntimeError("Failed to start Bloomberg session")

    # Drain startup events — any event confirms session is alive
    deadline = time.time() + 10
    started = False
    while time.time() < deadline:
        ev = c_void_p()
        lib.blpapi_Session_nextEvent(session, ctypes.byref(ev), 1000)
        if ev.value:
            started = True
            break

    if not started:
        lib.blpapi_Session_stop(session)
        lib.blpapi_Session_destroy(session)
        raise RuntimeError("Bloomberg session did not start")

    # Open refdata service
    svc_name = b"//blp/refdata"
    if lib.blpapi_Session_openService(session, svc_name) != 0:
        lib.blpapi_Session_stop(session)
        lib.blpapi_Session_destroy(session)
        raise RuntimeError("Failed to open //blp/refdata service")

    # Drain service open events
    deadline = time.time() + 10
    while time.time() < deadline:
        ev = c_void_p()
        lib.blpapi_Session_nextEvent(session, ctypes.byref(ev), 1000)
        if ev.value and lib.blpapi_Event_eventType(ev) in (
            BLPAPI_EVENTTYPE_REQUEST, BLPAPI_EVENTTYPE_RESPONSE,
            BLPAPI_EVENTTYPE_SESSION_STATUS
        ):
            break
        time.sleep(0.1)

    # Get service handle
    svc = c_void_p()
    if lib.blpapi_Session_getService(session, ctypes.byref(svc), svc_name) != 0:
        lib.blpapi_Session_stop(session)
        lib.blpapi_Session_destroy(session)
        raise RuntimeError("Failed to get //blp/refdata service handle")

    # Build ReferenceDataRequest
    req = c_void_p()
    lib.blpapi_Service_createRequest(svc, ctypes.byref(req), b"ReferenceDataRequest")
    root = lib.blpapi_Request_elements(req)

    # BLPAPI_ELEMENT_INDEX_END = append to array
    INDEX_END = 0xFFFFFFFF

    # Append securities
    sec_elem = c_void_p()
    lib.blpapi_Element_getElement(root, ctypes.byref(sec_elem), b"securities", None)
    for s in securities:
        lib.blpapi_Element_setValueString(sec_elem, s.encode(), INDEX_END)

    # Append fields
    fld_elem = c_void_p()
    lib.blpapi_Element_getElement(root, ctypes.byref(fld_elem), b"fields", None)
    for f in fields:
        lib.blpapi_Element_setValueString(fld_elem, f.encode(), INDEX_END)

    # Send
    lib.blpapi_Session_sendRequest(session, req, None, None, None, None, 0)
    lib.blpapi_Request_destroy(req)

    # Collect response
    result = {s: {} for s in securities}
    deadline = time.time() + timeout_ms / 1000
    done = False

    while not done and time.time() < deadline:
        ev = c_void_p()
        lib.blpapi_Session_nextEvent(session, ctypes.byref(ev), 500)
        if not ev.value:
            continue
        ev_type = lib.blpapi_Event_eventType(ev)

        if ev_type in (BLPAPI_EVENTTYPE_PARTIAL_RESPONSE, BLPAPI_EVENTTYPE_RESPONSE):
            it = lib.blpapi_MessageIterator_create(ev)
            msg_ptr = c_void_p()
            while lib.blpapi_MessageIterator_next(it, ctypes.byref(msg_ptr)) == 0:
                msg_elem = lib.blpapi_Message_elements(msg_ptr)
                if not msg_elem:
                    continue
                # securityData array
                sec_data_elem = c_void_p()
                if lib.blpapi_Element_getElement(msg_elem, ctypes.byref(sec_data_elem),
                                                  b"securityData", None) != 0:
                    continue
                n = lib.blpapi_Element_numValues(sec_data_elem)
                for i in range(n):
                    item = c_void_p()
                    lib.blpapi_Element_getElementAt(sec_data_elem, ctypes.byref(item), i)

                    # Get ticker
                    sec_name_elem = c_void_p()
                    lib.blpapi_Element_getElement(item, ctypes.byref(sec_name_elem),
                                                   b"security", None)
                    sec_sval = c_char_p()
                    lib.blpapi_Element_getValueAsString(sec_name_elem,
                                                        ctypes.byref(sec_sval), 0)
                    ticker = sec_sval.value.decode() if sec_sval.value else None

                    # Get fieldData
                    fd_elem = c_void_p()
                    lib.blpapi_Element_getElement(item, ctypes.byref(fd_elem),
                                                   b"fieldData", None)
                    if fd_elem and ticker and ticker in result:
                        result[ticker] = _read_element(lib, fd_elem) or {}

            lib.blpapi_MessageIterator_destroy(it)
            if ev_type == BLPAPI_EVENTTYPE_RESPONSE:
                done = True

    lib.blpapi_Session_stop(session)
    lib.blpapi_Session_destroy(session)
    return result


if __name__ == "__main__":
    # Quick smoke test
    print("Testing Bloomberg ctypes client...")
    data = bdp(
        securities=["CRWV US Equity", "GT10 Govt"],
        fields=["PX_LAST", "YLD_YTM_MID"],
    )
    for sec, vals in data.items():
        print(f"  {sec}: {vals}")
