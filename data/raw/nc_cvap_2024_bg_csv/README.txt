2024 Citizen Voting Age Population (CVAP) Data for North Carolina from the 2020-2024 American Community Survey (ACS) 5-Year Estimates at the Block Group level

## Redistricting Data Hub (RDH) Retrieval Date
02/11/2026

## Sources
CVAP data were retrieved from the U.S. Census Bureau Citizen Voting Age Population by Race and Ethnicity website: https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap.2024.html

## Fields
Field Name Description                                                                               
GEOID      12-digit unique identifier for the Block Group (state+county+tract+block group)
NAME       Full Geographic Name of the Block Group
STATE      Name of the State
COUNTY     Name of the County                                                                        
STATEFP    State FIPS Code                                                                           
COUNTYFP   County FIPS Code                                                                          
TRACTCE    Tract Code                                                                                
BLKGRPCE   Block Group Code                                                                          
C_TOT24    Citizen Estimate for Total                                                                
CTOTMOE    Citizen Margin of Error for Total                                                         
C_NHS24    Citizen Estimate for Not Hispanic or Latino                                               
CNHSMOE    Citizen Margin of Error for Not Hispanic or Latino                                        
C_AMI24    Citizen Estimate for American Indian or Alaska Native Alone                               
CAMIMOE    Citizen Margin of Error for American Indian or Alaska Native Alone                        
C_ASI24    Citizen Estimate for Asian Alone                                                          
CASIMOE    Citizen Margin of Error for Asian Alone                                                   
C_BLA24    Citizen Estimate for Black or African American Alone                                      
CBLAMOE    Citizen Margin of Error for Black or African American Alone                               
C_NHP24    Citizen Estimate for Native Hawaiian or Other Pacific Islander Alone                      
CNHPMOE    Citizen Margin of Error for Native Hawaiian or Other Pacific Islander Alone               
C_WHT24    Citizen Estimate for White Alone                                                          
CWHTMOE    Citizen Margin of Error for White Alone                                                   
C_AIW24    Citizen Estimate for American Indian or Alaska Native and White                           
CAIWMOE    Citizen Margin of Error for American Indian or Alaska Native and White                    
C_ASW24    Citizen Estimate for Asian and White                                                      
CASWMOE    Citizen Margin of Error for Asian and White                                               
C_BLW24    Citizen Estimate for Black or African American and White                                  
CBLWMOE    Citizen Margin of Error for Black or African American and White                           
C_AIB24    Citizen Estimate for American Indian or Alaska Native and Black or African American       
CAIBMOE    Citizen Margin of Error for American Indian or Alaska Native and Black or African American
C_2OM24    Citizen Estimate for Remainder of Two or More Race Responses                              
C2OMMOE    Citizen Margin of Error for Remainder of Two or More Race Responses                       
C_HSP24    Citizen Estimate for Hispanic or Latino                                                   
CHSPMOE    Citizen Margin of Error for Hispanic or Latino                                            
C_AIA24    Citizen Estimate for American Indian or Alaska Native Alone or In Combination             
CAIAMOE    Citizen Margin of Error for American Indian or Alaska Native Alone or In Combination      
C_ASN24    Citizen Estimate for Asian Alone or In Combination                                        
CASNMOE    Citizen Margin of Error for Asian Alone or In Combination                                 
C_BLK24    Citizen Estimate for Black or African American Alone or In Combination                    
CBLKMOE    Citizen Margin of Error for Black or African American Alone or In Combination             
CVAP_TOT24 CVAP Estimate for Total                                                                   
CVAPTOTMOE CVAP Margin of Error for Total                                                            
CVAP_NHS24 CVAP Estimate for Not Hispanic or Latino                                                  
CVAPNHSMOE CVAP Margin of Error for Not Hispanic or Latino                                           
CVAP_AMI24 CVAP Estimate for American Indian or Alaska Native Alone                                  
CVAPAMIMOE CVAP Margin of Error for American Indian or Alaska Native Alone                           
CVAP_ASI24 CVAP Estimate for Asian Alone                                                             
CVAPASIMOE CVAP Margin of Error for Asian Alone                                                      
CVAP_BLA24 CVAP Estimate for Black or African American Alone                                         
CVAPBLAMOE CVAP Margin of Error for Black or African American Alone                                  
CVAP_NHP24 CVAP Estimate for Native Hawaiian or Other Pacific Islander Alone                         
CVAPNHPMOE CVAP Margin of Error for Native Hawaiian or Other Pacific Islander Alone                  
CVAP_WHT24 CVAP Estimate for White Alone                                                             
CVAPWHTMOE CVAP Margin of Error for White Alone                                                      
CVAP_AIW24 CVAP Estimate for American Indian or Alaska Native and White                              
CVAPAIWMOE CVAP Margin of Error for American Indian or Alaska Native and White                       
CVAP_ASW24 CVAP Estimate for Asian and White                                                         
CVAPASWMOE CVAP Margin of Error for Asian and White                                                  
CVAP_BLW24 CVAP Estimate for Black or African American and White                                     
CVAPBLWMOE CVAP Margin of Error for Black or African American and White                              
CVAP_AIB24 CVAP Estimate for American Indian or Alaska Native and Black or African American          
CVAPAIBMOE CVAP Margin of Error for American Indian or Alaska Native and Black or African American   
CVAP_2OM24 CVAP Estimate for Remainder of Two or More Race Responses                                 
CVAP2OMMOE CVAP Margin of Error for Remainder of Two or More Race Responses                          
CVAP_HSP24 CVAP Estimate for Hispanic or Latino                                                      
CVAPHSPMOE CVAP Margin of Error for Hispanic or Latino                                               
CVAP_AIA24 CVAP Estimate for American Indian or Alaska Native Alone or In Combination                
CVAPAIAMOE CVAP Margin of Error for American Indian or Alaska Native Alone or In Combination         
CVAP_ASN24 CVAP Estimate for Asian Alone or In Combination                                           
CVAPASNMOE CVAP Margin of Error for Asian Alone or In Combination                                    
CVAP_BLK24 CVAP Estimate for Black or African American Alone or In Combination                       
CVAPBLKMOE CVAP Margin of Error for Black or African American Alone or In Combination 

## Processing
CVAP data for North Carolina were retrieved with a Python script from the U.S. Census Bureau. 
The data are available nationally at the Block Group level. 
To extract data for North Carolina, the national dataset was filtered by state and extracted to a new file for each state. 
The data were pivoted from long to wide format based on GEOIDs so that each row represents a single Block Group, and each field represents either an estimate or margin of error for a specific racial or ethnic category. 
Processing was primarily completed using the pandas library.
To improve the usefulness of the data, three categories were added to correspond with the Office of Management and Budget (OMB) racial categories. The "Alone or In Combination" categories for American Indian or Alaska Native (fields containing "AIA"), Asian (fields containing "ASN"), and Black or African American (fields containing "BLK") represent inclusive racial categories that encompass all estimates that include that race. For example, CVAP_AIA24 is the sum of CVAP_AMI24, CVAP_AIB24, and CVAP_AIW24. CVAP_BLK24 is the sum of CVAP_BLA24, CVAP_AIB24, and CVAP_BLW24. CVAP_ASN24 is the sum of CVAP_ASI24 and CVAP_ASW24. No other estimate categories were modified.
For estimates that were modified to fit OMB racial/ethnic categories, the margins of error (MOEs) were also recalculated by summing the squared MOEs of the component fields and taking the square root of the sum. These modified MOEs correspond to the derived racial categories and are rounded to the nearest hundredth.
All racial estimates provided are Non-Hispanic. Breakdowns for Hispanic/Non-Hispanic by race are not provided in the CVAP special tabulation.
Null values or empty cells in the CSV file retrieved from the U.S. Census Bureau are assigned the value -999999.

## Additional Notes
Block Group (summary level 150, based on boundaries as of January 1, 2020).
For more information on the ACS CVAP documentation, please refer to the ACS link above in Sources, as well as the ACS technical documentation included in this folder (also available at this link: https://www2.census.gov/programs-surveys/decennial/rdo/technical-documentation/special-tabulation/CVAP_2020-2024_ACS_documentation_v1.pdf ).
Please note that this dataset is derived from data collected in the five-year range 2020-2024. The U.S. Census Bureau recommends against using different datasets that contain overlapping years. For more information, please see https://www.census.gov/newsroom/blogs/random-samplings/2022/03/period-estimates-american-community-survey.html
Please direct questions related to processing this dataset to info@redistrictingdatahub.org.

