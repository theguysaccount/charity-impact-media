"""Synthetic Form 990 e-file returns shaped like real IRS XML (same namespace, tags and
nesting). The people in them are invented; tests assert that none of their names reach
the parse cache or the built site."""

PEOPLE = ["JANE Q DOE", "JOHN SMITH", "MARY JONES", "ROBERT BROWN"]


def return_xml(ein="123456789", name="EXAMPLE RELIEF FUND INC", tax_year=2024, period_end="2025-06-30",
               return_ts="2025-11-10T10:00:00-05:00", rev=12_000_000, contrib=9_000_000, gov=1_000_000,
               prog_rev=2_500_000, inv=300_000, exp=10_000_000, prog=8_500_000, mgmt=900_000, fund=600_000,
               ceo=350_000, amended=False, dba="", mission="PROVIDES DISASTER RELIEF AND RECOVERY SERVICES.",
               program_desc="EMERGENCY SHELTER - SEE SCHEDULE O"):
    other_rev = rev - contrib - prog_rev - inv
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Return xmlns="http://www.irs.gov/efile" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" returnVersion="2024v5.0">
  <ReturnHeader binaryAttachmentCnt="0">
    <ReturnTs>{return_ts}</ReturnTs>
    <TaxPeriodEndDt>{period_end}</TaxPeriodEndDt>
    <TaxPeriodBeginDt>{tax_year}-07-01</TaxPeriodBeginDt>
    <Filer>
      <EIN>{ein}</EIN>
      <BusinessName><BusinessNameLine1Txt>{name}</BusinessNameLine1Txt></BusinessName>
      <PhoneNum>5555550100</PhoneNum>
      <USAddress><AddressLine1Txt>1 MAIN ST</AddressLine1Txt><CityNm>SPRINGFIELD</CityNm><StateAbbreviationCd>IL</StateAbbreviationCd><ZIPCd>62701</ZIPCd></USAddress>
    </Filer>
    <BusinessOfficerGrp><PersonNm>{PEOPLE[0]}</PersonNm><PersonTitleTxt>CEO</PersonTitleTxt><PhoneNum>5555550100</PhoneNum></BusinessOfficerGrp>
    <TaxYr>{tax_year}</TaxYr>
  </ReturnHeader>
  <ReturnData documentCnt="2">
    <IRS990 documentId="RetDoc1">
      <PrincipalOfficerNm>{PEOPLE[0]}</PrincipalOfficerNm>
      {"<AmendedReturnInd>X</AmendedReturnInd>" if amended else ""}
      {f"<DoingBusinessAsName><BusinessNameLine1Txt>{dba}</BusinessNameLine1Txt></DoingBusinessAsName>" if dba else ""}
      <GrossReceiptsAmt>{rev}</GrossReceiptsAmt>
      <GroupReturnForAffiliatesInd>false</GroupReturnForAffiliatesInd>
      <Organization501c3Ind>X</Organization501c3Ind>
      <WebsiteAddressTxt>WWW.EXAMPLE.ORG</WebsiteAddressTxt>
      <FormationYr>1985</FormationYr>
      <ActivityOrMissionDesc>{mission}</ActivityOrMissionDesc>
      <VotingMembersGoverningBodyCnt>12</VotingMembersGoverningBodyCnt>
      <VotingMembersIndependentCnt>11</VotingMembersIndependentCnt>
      <TotalEmployeeCnt>140</TotalEmployeeCnt>
      <TotalVolunteersCnt>900</TotalVolunteersCnt>
      <CYContributionsGrantsAmt>{contrib}</CYContributionsGrantsAmt>
      <CYProgramServiceRevenueAmt>{prog_rev}</CYProgramServiceRevenueAmt>
      <CYInvestmentIncomeAmt>{inv}</CYInvestmentIncomeAmt>
      <CYOtherRevenueAmt>{other_rev}</CYOtherRevenueAmt>
      <CYTotalRevenueAmt>{rev}</CYTotalRevenueAmt>
      <CYGrantsAndSimilarPaidAmt>400000</CYGrantsAndSimilarPaidAmt>
      <CYSalariesCompEmpBnftPaidAmt>6000000</CYSalariesCompEmpBnftPaidAmt>
      <CYTotalExpensesAmt>{exp}</CYTotalExpensesAmt>
      <TotalAssetsEOYAmt>20000000</TotalAssetsEOYAmt>
      <TotalLiabilitiesEOYAmt>5000000</TotalLiabilitiesEOYAmt>
      <NetAssetsOrFundBalancesEOYAmt>15000000</NetAssetsOrFundBalancesEOYAmt>
      <MissionDesc>{mission}</MissionDesc>
      <ExpenseAmt>{prog - 1_500_000}</ExpenseAmt>
      <GrantAmt>100000</GrantAmt>
      <RevenueAmt>200000</RevenueAmt>
      <Desc>{program_desc}</Desc>
      <ProgSrvcAccomActy2Grp><ExpenseAmt>1000000</ExpenseAmt><RevenueAmt>0</RevenueAmt><Desc>FOOD DISTRIBUTION TO 40,000 FAMILIES.</Desc></ProgSrvcAccomActy2Grp>
      <TotalOtherProgSrvcExpenseAmt>500000</TotalOtherProgSrvcExpenseAmt>
      <TotalProgramServiceExpensesAmt>{prog}</TotalProgramServiceExpensesAmt>
      <LobbyingActivitiesInd>false</LobbyingActivitiesInd>
      <DonorAdvisedFundInd>false</DonorAdvisedFundInd>
      <ProfessionalFundraisingInd>true</ProfessionalFundraisingInd>
      <ForeignActivitiesInd>false</ForeignActivitiesInd>
      <EngagedInExcessBenefitTransInd>false</EngagedInExcessBenefitTransInd>
      <LoanOutstandingInd>false</LoanOutstandingInd>
      <FamilyOrBusinessRlnInd>false</FamilyOrBusinessRlnInd>
      <MaterialDiversionOrMisuseInd>false</MaterialDiversionOrMisuseInd>
      <Form990ProvidedToGvrnBodyInd>true</Form990ProvidedToGvrnBodyInd>
      <ConflictOfInterestPolicyInd>true</ConflictOfInterestPolicyInd>
      <WhistleblowerPolicyInd>true</WhistleblowerPolicyInd>
      <DocumentRetentionPolicyInd>false</DocumentRetentionPolicyInd>
      <CompensationProcessCEOInd>true</CompensationProcessCEOInd>
      <BooksInCareOfDetail><PersonNm>{PEOPLE[3]}</PersonNm><PhoneNum>5555550101</PhoneNum></BooksInCareOfDetail>
      <Form990PartVIISectionAGrp>
        <PersonNm>{PEOPLE[0]}</PersonNm><TitleTxt>PRESIDENT &amp; CEO (JANE DOE)</TitleTxt><AverageHoursPerWeekRt>50.00</AverageHoursPerWeekRt>
        <OfficerInd>X</OfficerInd><ReportableCompFromOrgAmt>{ceo}</ReportableCompFromOrgAmt><ReportableCompFromRltdOrgAmt>0</ReportableCompFromRltdOrgAmt><OtherCompensationAmt>40000</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
      <Form990PartVIISectionAGrp>
        <PersonNm>{PEOPLE[1]}</PersonNm><TitleTxt>CFO</TitleTxt><AverageHoursPerWeekRt>40.00</AverageHoursPerWeekRt>
        <OfficerInd>X</OfficerInd><ReportableCompFromOrgAmt>210000</ReportableCompFromOrgAmt><ReportableCompFromRltdOrgAmt>15000</ReportableCompFromRltdOrgAmt><OtherCompensationAmt>20000</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
      <Form990PartVIISectionAGrp>
        <PersonNm>{PEOPLE[2]}</PersonNm><TitleTxt>BOARD CHAIR</TitleTxt><AverageHoursPerWeekRt>2.00</AverageHoursPerWeekRt>
        <IndividualTrusteeOrDirectorInd>X</IndividualTrusteeOrDirectorInd><ReportableCompFromOrgAmt>0</ReportableCompFromOrgAmt><ReportableCompFromRltdOrgAmt>0</ReportableCompFromRltdOrgAmt><OtherCompensationAmt>0</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
      <IndivRcvdGreaterThan100KCnt>9</IndivRcvdGreaterThan100KCnt>
      <ContractorCompensationGrp><ContractorName><BusinessName><BusinessNameLine1Txt>ACME DIRECT MAIL LLC</BusinessNameLine1Txt></BusinessName></ContractorName><ServicesDesc>DIRECT MAIL</ServicesDesc><CompensationAmt>450000</CompensationAmt></ContractorCompensationGrp>
      <ContractorCompensationGrp><ContractorName><PersonNm>{PEOPLE[2]}</PersonNm></ContractorName><ServicesDesc>CONSULTING</ServicesDesc><CompensationAmt>300000</CompensationAmt></ContractorCompensationGrp>
      <ContractorCompensationGrp><ContractorName><BusinessName><BusinessNameLine1Txt>ROBERT BROWN CONSULTING LLC</BusinessNameLine1Txt></BusinessName></ContractorName><ServicesDesc>STRATEGY</ServicesDesc><CompensationAmt>200000</CompensationAmt></ContractorCompensationGrp>
      <CntrctRcvdGreaterThan100KCnt>4</CntrctRcvdGreaterThan100KCnt>
      <FederatedCampaignsAmt>100000</FederatedCampaignsAmt>
      <GovernmentGrantsAmt>{gov}</GovernmentGrantsAmt>
      <AllOtherContributionsAmt>{contrib - gov - 100000}</AllOtherContributionsAmt>
      <TotalContributionsAmt>{contrib}</TotalContributionsAmt>
      <TotalProgramServiceRevenueAmt>{prog_rev}</TotalProgramServiceRevenueAmt>
      <CompCurrentOfcrDirectorsGrp><TotalAmt>600000</TotalAmt></CompCurrentOfcrDirectorsGrp>
      <FeesForServicesProfFundraising><TotalAmt>200000</TotalAmt><FundraisingAmt>200000</FundraisingAmt></FeesForServicesProfFundraising>
      <TotalFunctionalExpensesGrp><TotalAmt>{exp}</TotalAmt><ProgramServicesAmt>{prog}</ProgramServicesAmt><ManagementAndGeneralAmt>{mgmt}</ManagementAndGeneralAmt><FundraisingAmt>{fund}</FundraisingAmt></TotalFunctionalExpensesGrp>
      <TotalAssetsGrp><BOYAmt>19000000</BOYAmt><EOYAmt>20000000</EOYAmt></TotalAssetsGrp>
      <TotalLiabilitiesGrp><BOYAmt>5000000</BOYAmt><EOYAmt>5000000</EOYAmt></TotalLiabilitiesGrp>
      <NoDonorRestrictionNetAssetsGrp><BOYAmt>9000000</BOYAmt><EOYAmt>10000000</EOYAmt></NoDonorRestrictionNetAssetsGrp>
      <TotalNetAssetsFundBalanceGrp><BOYAmt>14000000</BOYAmt><EOYAmt>15000000</EOYAmt></TotalNetAssetsFundBalanceGrp>
      <FSAuditedInd>true</FSAuditedInd>
      <AuditCommitteeInd>true</AuditCommitteeInd>
    </IRS990>
    <IRS990ScheduleO documentId="RetDoc2"><SupplementalInformationDetail><FormAndLineReferenceDesc>PART VI</FormAndLineReferenceDesc><ExplanationTxt>CONTACT {PEOPLE[3]}</ExplanationTxt></SupplementalInformationDetail></IRS990ScheduleO>
  </ReturnData>
</Return>
""".encode("utf-8")


def ez_xml():
    return b"""<?xml version="1.0" encoding="utf-8"?><Return xmlns="http://www.irs.gov/efile" returnVersion="2024v5.0"><ReturnHeader><TaxYr>2024</TaxYr><Filer><EIN>111111111</EIN></Filer></ReturnHeader><ReturnData><IRS990EZ><TotalRevenueAmt>100</TotalRevenueAmt></IRS990EZ></ReturnData></Return>"""
