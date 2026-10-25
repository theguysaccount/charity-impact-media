"""Parse one IRS Form 990 e-file XML return into a compact summary.

    from parse990 import parse
    rec = parse(xml_bytes)          # dict, or None when the return is not a Form 990

Every amount keeps the Form 990 part and line it came from (see FIELD_SOURCES), so the
site can cite it. Privacy by design: Part VII person names (PersonNm), the principal
officer, the books-in-care-of contact and phone numbers are never read. Titles keep
only role words, and contractor names are kept only when no part could be a person.
"""

import re
import xml.etree.ElementTree as ET

from common import clip, fmt_ein, money, safe_business_name, safe_title

PARSER_VERSION = 3

# Where each published figure sits on the form (shown next to the number on the site).
FIELD_SOURCES = {
    "rev_total": "Part I, line 12", "contributions": "Part VIII, line 1h", "gov_grants": "Part VIII, line 1e",
    "federated": "Part VIII, line 1a", "membership_dues": "Part VIII, line 1b", "event_contrib": "Part VIII, line 1c",
    "related_orgs": "Part VIII, line 1d", "other_contrib": "Part VIII, line 1f", "noncash": "Part VIII, line 1g",
    "program_rev": "Part VIII, line 2g", "investment": "Part VIII, line 3", "other_rev": "Part I, line 11",
    "exp_total": "Part IX, line 25(A)", "exp_program": "Part IX, line 25(B)", "exp_mgmt": "Part IX, line 25(C)",
    "exp_fundraising": "Part IX, line 25(D)", "grants_paid": "Part I, line 13", "salaries": "Part I, line 15",
    "prof_fundraising": "Part IX, line 11e", "officer_comp": "Part IX, line 5", "assets": "Part X, line 16(B)",
    "liabilities": "Part X, line 26(B)", "net_assets": "Part X, line 33(B)", "net_assets_free": "Part X, line 27(B)",
    "comp": "Part VII, Section A", "n_over_100k": "Part VII, line 2", "contractors": "Part VII, Section B",
    "programs": "Part III, lines 4a-4e", "employees": "Part I, line 5", "volunteers": "Part I, line 6",
    "board": "Part VI, lines 1a-1b", "governance": "Part VI, lines 12-15", "audited": "Part XII, line 2b",
}


def _strip(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _t(el, path):
    if el is None:
        return ""
    x = el.find(path)
    return " ".join(x.text.split()) if x is not None and x.text else ""


def _m(el, path):
    v = _t(el, path)
    return money(v) if v else None


def _b(el, path):
    v = _t(el, path).lower()
    if not v:
        return None
    return v in ("true", "1", "x", "yes")


def _first_m(el, *paths):
    for p in paths:
        v = _m(el, p)
        if v is not None:
            return v
    return None


def _program(el):
    if el is None:
        return None
    desc = _t(el, "Desc")
    exp = _m(el, "ExpenseAmt")
    if not desc and not exp:
        return None
    return {"desc": clip(desc, 900), "exp": exp, "grants": _m(el, "GrantAmt"), "rev": _m(el, "RevenueAmt")}


def parse(xml_bytes):
    root = _strip(ET.fromstring(xml_bytes))
    hdr = root.find("ReturnHeader")
    f = root.find("ReturnData/IRS990")
    if f is None or hdr is None:
        return None
    filer = hdr.find("Filer")
    name1 = _t(filer, "BusinessName/BusinessNameLine1Txt") or _t(filer, "BusinessName/BusinessNameLine1")
    name2 = _t(filer, "BusinessName/BusinessNameLine2Txt")
    us = filer.find("USAddress") if filer is not None else None

    rec = {
        "v": PARSER_VERSION,
        "ein": fmt_ein(_t(filer, "EIN")),
        "tax_year": int(_t(hdr, "TaxYr") or 0) or None,
        "period_begin": _t(hdr, "TaxPeriodBeginDt"),
        "period_end": _t(hdr, "TaxPeriodEndDt"),
        "return_ts": _t(hdr, "ReturnTs"),
        "return_version": root.get("returnVersion", ""),
        "name": name1, "name2": name2,
        "dba": _t(f, "DoingBusinessAsName/BusinessNameLine1Txt"),
        "city": _t(us, "CityNm"), "state": _t(us, "StateAbbreviationCd"),
        "website": _t(f, "WebsiteAddressTxt")[:120],
        "formation_year": int(_t(f, "FormationYr") or 0) or None,
        "domicile": _t(f, "LegalDomicileStateCd"),
        "amended": _b(f, "AmendedReturnInd") or False,
        "group_return": _b(f, "GroupReturnForAffiliatesInd") or False,
        "mission": clip(_t(f, "MissionDesc") or _t(f, "ActivityOrMissionDesc"), 600),
        "employees": _m(f, "TotalEmployeeCnt"),
        "volunteers": _m(f, "TotalVolunteersCnt"),
        "board_voting": _first_m(f, "GoverningBodyVotingMembersCnt", "VotingMembersGoverningBodyCnt"),
        "board_independent": _first_m(f, "IndependentVotingMemberCnt", "VotingMembersIndependentCnt"),
        # Revenue (Part I / Part VIII)
        "rev_total": _first_m(f, "CYTotalRevenueAmt", "TotalRevenueGrp/TotalRevenueColumnAmt"),
        "contributions": _first_m(f, "TotalContributionsAmt", "CYContributionsGrantsAmt"),
        "gov_grants": _m(f, "GovernmentGrantsAmt"),
        "federated": _m(f, "FederatedCampaignsAmt"),
        "membership_dues": _m(f, "MembershipDuesAmt"),
        "event_contrib": _m(f, "FundraisingAmt"),
        "related_orgs": _m(f, "RelatedOrganizationsAmt"),
        "other_contrib": _m(f, "AllOtherContributionsAmt"),
        "noncash": _m(f, "NoncashContributionsAmt"),
        "program_rev": _first_m(f, "CYProgramServiceRevenueAmt", "TotalProgramServiceRevenueAmt"),
        "investment": _m(f, "CYInvestmentIncomeAmt"),
        "other_rev": _m(f, "CYOtherRevenueAmt"),
        # Expenses (Part I / Part IX)
        "exp_total": _first_m(f, "TotalFunctionalExpensesGrp/TotalAmt", "CYTotalExpensesAmt"),
        "exp_program": _first_m(f, "TotalFunctionalExpensesGrp/ProgramServicesAmt", "TotalProgramServiceExpensesAmt"),
        "exp_mgmt": _m(f, "TotalFunctionalExpensesGrp/ManagementAndGeneralAmt"),
        "exp_fundraising": _m(f, "TotalFunctionalExpensesGrp/FundraisingAmt"),
        "grants_paid": _m(f, "CYGrantsAndSimilarPaidAmt"),
        "salaries": _m(f, "CYSalariesCompEmpBnftPaidAmt"),
        "prof_fundraising": _first_m(f, "FeesForServicesProfFundraising/TotalAmt", "CYTotalProfFndrsngExpnsAmt"),
        "officer_comp": _m(f, "CompCurrentOfcrDirectorsGrp/TotalAmt"),
        "grants_domestic_orgs": _m(f, "GrantsToDomesticOrgsGrp/TotalAmt"),
        "grants_domestic_people": _m(f, "GrantsToDomesticIndividualsGrp/TotalAmt"),
        "grants_foreign": _m(f, "ForeignGrantsGrp/TotalAmt"),
        "advertising": _m(f, "AdvertisingGrp/TotalAmt"),
        # Balance sheet (Part X, end of year)
        "assets": _first_m(f, "TotalAssetsGrp/EOYAmt", "TotalAssetsEOYAmt"),
        "liabilities": _first_m(f, "TotalLiabilitiesGrp/EOYAmt", "TotalLiabilitiesEOYAmt"),
        "net_assets": _first_m(f, "TotalNetAssetsFundBalanceGrp/EOYAmt", "NetAssetsOrFundBalancesEOYAmt"),
        "net_assets_free": _first_m(f, "NoDonorRestrictionNetAssetsGrp/EOYAmt", "UnrestrictedNetAssetsGrp/EOYAmt"),
        "cash": (_m(f, "CashNonInterestBearingGrp/EOYAmt") or 0) + (_m(f, "SavingsAndTempCashInvstGrp/EOYAmt") or 0),
        # Part IV / VI / XII facts, as answered by the organization
        "f": {
            "conflict_policy": _b(f, "ConflictOfInterestPolicyInd"),
            "whistleblower": _b(f, "WhistleblowerPolicyInd"),
            "doc_retention": _b(f, "DocumentRetentionPolicyInd"),
            "ceo_comp_process": _b(f, "CompensationProcessCEOInd"),
            "other_comp_process": _b(f, "CompensationProcessOtherInd"),
            "board_saw_990": _b(f, "Form990ProvidedToGvrnBodyInd"),
            "minutes": _b(f, "MinutesOfGoverningBodyInd"),
            "family_business": _b(f, "FamilyOrBusinessRlnInd"),
            "diversion": _b(f, "MaterialDiversionOrMisuseInd"),
            "excess_benefit": _b(f, "EngagedInExcessBenefitTransInd"),
            "loans_insiders": _b(f, "LoanOutstandingInd"),
            "audited": _b(f, "FSAuditedInd"),
            "audit_committee": _b(f, "AuditCommitteeInd"),
            "lobbying": _b(f, "LobbyingActivitiesInd"),
            "political": _b(f, "PoliticalCampaignActyInd"),
            "daf": _b(f, "DonorAdvisedFundInd"),
            "hospital": _b(f, "OperateHospitalInd"),
            "school": _b(f, "SchoolOperatingInd"),
            "foreign": _b(f, "ForeignActivitiesInd"),
            "prof_fundraisers": _b(f, "ProfessionalFundraisingInd"),
        },
        "n_over_100k": _m(f, "IndivRcvdGreaterThan100KCnt"),
        "n_contractors_100k": _m(f, "CntrctRcvdGreaterThan100KCnt"),
    }

    # Part III: the three largest programs plus "other" (4d).
    progs = [_program(f)]  # 4a sits directly under IRS990
    progs += [_program(f.find("ProgSrvcAccomActy2Grp")), _program(f.find("ProgSrvcAccomActy3Grp"))]
    progs = [p for p in progs if p]
    other = [_program(x) for x in f.findall("ProgSrvcAccomActyOtherGrp")]
    other_exp = _m(f, "TotalOtherProgSrvcExpenseAmt")
    rec["programs"] = progs
    rec["programs_other_exp"] = other_exp if other_exp is not None else sum((p or {}).get("exp") or 0 for p in other) or None
    rec["programs_total_exp"] = _m(f, "TotalProgramServiceExpensesAmt")

    # Part VII Section A: compensation by role. Names are never read.
    comp = []
    for g in f.findall("Form990PartVIISectionAGrp"):
        org, rel, oth = _m(g, "ReportableCompFromOrgAmt") or 0, _m(g, "ReportableCompFromRltdOrgAmt") or 0, _m(g, "OtherCompensationAmt") or 0
        total = org + rel + oth
        roles = "".join(k for k, tag in (("D", "IndividualTrusteeOrDirectorInd"), ("D", "InstitutionalTrusteeInd"),
                                         ("O", "OfficerInd"), ("K", "KeyEmployeeInd"),
                                         ("H", "HighestCompensatedEmployeeInd"), ("F", "FormerOfcrDirectorTrusteeInd"))
                        if _b(g, tag))
        title = safe_title(_t(g, "TitleTxt"))
        comp.append({"title": title, "roles": roles, "hours": _t(g, "AverageHoursPerWeekRt"),
                     "org": org, "related": rel, "other": oth, "total": total})
    comp.sort(key=lambda c: (-c["total"], c["title"]))
    rec["n_listed"] = len(comp)
    rec["n_listed_paid"] = sum(1 for c in comp if c["total"] > 0)
    rec["comp_listed_total"] = sum(c["total"] for c in comp)
    rec["comp"] = [c for c in comp if c["total"] > 0][:10]

    # Part VII Section B: five highest-paid independent contractors (businesses only).
    cons = []
    for g in f.findall("ContractorCompensationGrp"):
        nm = _t(g, "ContractorName/BusinessName/BusinessNameLine1Txt") or _t(g, "ContractorName/BusinessName/BusinessNameLine1")
        nm2 = _t(g, "ContractorName/BusinessName/BusinessNameLine2Txt")
        if not nm:
            continue  # a person (ContractorName/PersonNm): never read
        safe = safe_business_name((nm + " " + nm2).strip() if nm2 and not nm2.upper().startswith(("C/O", "ATTN", "%")) else nm)
        if not safe:
            continue
        cons.append({"name": safe[:90], "services": clip(_t(g, "ServicesDesc"), 80), "amount": _m(g, "CompensationAmt") or 0})
    cons.sort(key=lambda c: -c["amount"])
    rec["contractors"] = cons[:5]
    return rec


def ein_of(xml_bytes):
    """Cheap EIN sniff without a full parse (for logging)."""
    m = re.search(rb"<EIN>(\d{9})</EIN>", xml_bytes[:4000])
    return m.group(1).decode() if m else ""
