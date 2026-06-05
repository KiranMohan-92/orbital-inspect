"""CCSDS Conjunction Data Message (CDM) parser — KVN (Key-Value Notation).

Reference: CCSDS 508.0-B-1, "Conjunction Data Message".

This is a SPIKE parser focused on the subset of fields needed for analytic
probability-of-collision (Pc) screening:

  * Relative metadata (TCA, MISS_DISTANCE, RELATIVE_SPEED, RELATIVE_POSITION_*).
  * Per-object state vectors (X, Y, Z [km], X_DOT, Y_DOT, Z_DOT [km/s]).
  * Per-object RTN (a.k.a. RIC / RSW) position covariance lower-triangle:
        CR_R, CT_R, CT_T, CN_R, CN_T, CN_N   (units km^2).

Frame convention
----------------
The CCSDS covariance block is expressed in the RTN frame of each object:
  R = radial, T = transverse (along-track-ish), N = normal (cross-track).
CCSDS orders the covariance lower-triangle as R, T, N. The 3x3 position
covariance is therefore:

        | CR_R   CT_R   CN_R |
    P = | CT_R   CT_T   CN_T |
        | CN_R   CN_T   CN_N |

We deliberately keep this tolerant of missing fields and unit suffixes so the
fail-closed Pc path (see pc.py) can reason about absent/garbage covariance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Tuple

import numpy as np


# Covariance terms (CCSDS RTN lower-triangle) required to build the 3x3
# position covariance. If ANY are missing we treat the covariance as absent.
_COV_TERMS = ("CR_R", "CT_R", "CT_T", "CN_R", "CN_T", "CN_N")


@dataclass
class CdmObject:
    """One conjunction participant (OBJECT1 or OBJECT2)."""

    object_label: str = ""            # "OBJECT1" / "OBJECT2"
    object_designator: Optional[str] = None
    object_name: Optional[str] = None

    # State vector (km, km/s) in the message's reference frame.
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    x_dot: Optional[float] = None
    y_dot: Optional[float] = None
    z_dot: Optional[float] = None

    # RTN position covariance lower-triangle (km^2). None => absent.
    cr_r: Optional[float] = None
    ct_r: Optional[float] = None
    ct_t: Optional[float] = None
    cn_r: Optional[float] = None
    cn_t: Optional[float] = None
    cn_n: Optional[float] = None

    def position_covariance_rtn(self) -> Optional[np.ndarray]:
        """Return the symmetric 3x3 RTN position covariance (km^2).

        Returns None if any required covariance term is absent — this is what
        drives the fail-closed behaviour downstream.
        """
        vals = (self.cr_r, self.ct_r, self.ct_t, self.cn_r, self.cn_t, self.cn_n)
        if any(v is None for v in vals):
            return None
        cr_r, ct_r, ct_t, cn_r, cn_t, cn_n = vals
        return np.array(
            [
                [cr_r, ct_r, cn_r],
                [ct_r, ct_t, cn_t],
                [cn_r, cn_t, cn_n],
            ],
            dtype=float,
        )


@dataclass
class Cdm:
    """Parsed Conjunction Data Message (subset)."""

    tca: Optional[str] = None
    miss_distance_m: Optional[float] = None
    relative_speed_m_s: Optional[float] = None
    relative_position_rtn_m: Optional[np.ndarray] = None  # 3-vector [R, T, N], metres
    hard_body_radius_m: Optional[float] = None
    sat1: CdmObject = field(default_factory=CdmObject)
    sat2: CdmObject = field(default_factory=CdmObject)
    creation_date: Optional[str] = None
    ccsds_cdm_vers: Optional[str] = None


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #


def _split_key_value(line: str) -> Optional[Tuple[str, str]]:
    """Split a KVN line `KEY = VALUE [UNIT]` -> (KEY, VALUE_WITH_UNIT_STRIPPED).

    Returns None for comments / blank / malformed lines.
    """
    line = line.strip()
    if not line or line.startswith("COMMENT") or line.startswith("#"):
        return None
    if "=" not in line:
        return None
    key, _, raw_val = line.partition("=")
    return key.strip().upper(), raw_val.strip()


def _to_float(raw_val: str) -> Optional[float]:
    """Parse a numeric KVN value, tolerating a trailing unit token.

    e.g. "7000.123 [km]"  -> 7000.123
         "1.2e-3"          -> 0.0012
         "-543.0 km"       -> -543.0
    Returns None if the leading token is not numeric.
    """
    if raw_val is None:
        return None
    s = raw_val.strip()
    # Strip a bracketed unit if present: "12.3 [km]" -> "12.3"
    if "[" in s:
        s = s.split("[", 1)[0].strip()
    # First whitespace-separated token is the number; the rest (if any) is a unit.
    token = s.split()[0] if s.split() else s
    try:
        return float(token)
    except ValueError:
        return None


# Map CCSDS covariance keys to CdmObject attribute names.
_COV_ATTR = {
    "CR_R": "cr_r",
    "CT_R": "ct_r",
    "CT_T": "ct_t",
    "CN_R": "cn_r",
    "CN_T": "cn_t",
    "CN_N": "cn_n",
}

# State vector keys.
_STATE_ATTR = {
    "X": "x",
    "Y": "y",
    "Z": "z",
    "X_DOT": "x_dot",
    "Y_DOT": "y_dot",
    "Z_DOT": "z_dot",
}


def parse_cdm_kvn(text: str) -> Cdm:
    """Parse a CCSDS CDM in KVN text into a :class:`Cdm`.

    The parser walks lines top-to-bottom. A line `OBJECT = OBJECT1` (or the key
    `OBJECT_DESIGNATOR` appearing after such a marker) switches the "current
    object" context so that subsequent state/covariance keys are attributed to
    the right participant. Relative-metadata keys (TCA, MISS_DISTANCE, ...) are
    parsed regardless of context.
    """
    cdm = Cdm()
    rel_r = rel_t = rel_n = None

    # current_obj is None while in the header/relative-metadata section.
    current_obj: Optional[CdmObject] = None

    for raw_line in text.splitlines():
        kv = _split_key_value(raw_line)
        if kv is None:
            continue
        key, val = kv

        # --- object section switching ---------------------------------- #
        if key == "OBJECT":
            label = val.strip().upper()
            if label in ("OBJECT1", "1", "SAT1"):
                current_obj = cdm.sat1
                cdm.sat1.object_label = "OBJECT1"
            elif label in ("OBJECT2", "2", "SAT2"):
                current_obj = cdm.sat2
                cdm.sat2.object_label = "OBJECT2"
            continue

        # --- header / relative metadata --------------------------------- #
        if key == "CCSDS_CDM_VERS":
            cdm.ccsds_cdm_vers = val
            continue
        if key == "CREATION_DATE":
            cdm.creation_date = val
            continue
        if key == "TCA":
            cdm.tca = val
            continue
        if key == "MISS_DISTANCE":
            # CCSDS default unit is metres for MISS_DISTANCE.
            cdm.miss_distance_m = _to_float(val)
            continue
        if key == "RELATIVE_SPEED":
            cdm.relative_speed_m_s = _to_float(val)  # m/s
            continue
        if key == "RELATIVE_POSITION_R":
            rel_r = _to_float(val)
            continue
        if key == "RELATIVE_POSITION_T":
            rel_t = _to_float(val)
            continue
        if key == "RELATIVE_POSITION_N":
            rel_n = _to_float(val)
            continue
        if key in ("HBR", "HARD_BODY_RADIUS"):
            cdm.hard_body_radius_m = _to_float(val)
            continue

        # --- per-object fields ------------------------------------------ #
        if current_obj is not None:
            if key == "OBJECT_DESIGNATOR":
                current_obj.object_designator = val
                continue
            if key == "OBJECT_NAME":
                current_obj.object_name = val
                continue
            if key in _STATE_ATTR:
                setattr(current_obj, _STATE_ATTR[key], _to_float(val))
                continue
            if key in _COV_ATTR:
                setattr(current_obj, _COV_ATTR[key], _to_float(val))
                continue
        # Unknown / unhandled key -> ignore (tolerant parser).

    if rel_r is not None and rel_t is not None and rel_n is not None:
        cdm.relative_position_rtn_m = np.array([rel_r, rel_t, rel_n], dtype=float)

    return cdm
