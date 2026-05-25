Include HS.FHIRServer
Class PCMHack.FHIRServer.OAuth2Token Extends HS.FHIRServer.Util.OAuth2Token
{



/// Derives context values (e.g., patient context) from the access token JWT object
/// information. Default functionality is to derive it from scopes that are
/// formatted as "launch/" _ contextName _ "/" _ contextValue, or from a specific
/// JWT property such as "patient".
Method SetContextValues() [ Private ]
{
    // *** IL PCM ***
    // overriding this method to enable the Patient external Identifier to internal Resource ID mapping
    //-------------------------------------------
	do ##super()

    set originalPatient = $GET(..%ContextValues("patient"))

    $$$FSLog("original patient iden in Context = "_originalPatient)

    if originalPatient'="" {		
		set patientResourceId = ##class(PCMHack.Util.Utils).GetPatientResourceId(..%interactions.strategy,originalPatient)
        $$$FSLog("found patient resource id = "_patientResourceId)
        if patientResourceId = "" {
            // if we didn't find a patient Id, we don't want to leave it empty so we'll use a "fake" id so it will return no result, or fail, as desired
            set patientResourceId="xxxxyyyzzz"
        }
        set ..%ContextValues("patient")=patientResourceId       
    }
    
    $$$FSLog("patient id in Context after change = "_$GET(..%ContextValues("patient")))
}





/// Uses the instance properties populated by SetInstance() to validate the access
/// token and to derive and expose access token data that will be used for verifying
/// that a given FHIR request is allowed by the token. If ValidateToken() fails then
/// it will Throw. Otherwise, it will simply Return.
Method ValidateToken() [ Private ]
{
    // *** IL PCM ***
    // overriding this method for now to prevent what looks like a superflous JWT validation in case Introspection returned a full JSON, and the original token was opaque
    //-------------------------------------------

	#define dynPropToString(%p) $Select($IsObject(%p):%p.%ToJSON(), 1:%p)
	
	$$$FSLog("BaseURL=" _ ..BaseURL)
	
	// Attempt token introspection first.
	Set introStatus = ..GetIntrospection(.introJWTObj)
	
	$$$FSLog("GetIntrospection returned status = " _ $Select($$$ISERR(introStatus):$system.Status.GetErrorText(introStatus), 1:1))
	
	If $$$ISOK(introStatus) {
		
		If $IsObject(introJWTObj) {
			// Guard against customization returning object without active.
			If introJWTObj.active {	
				Set ..%TokenObject = introJWTObj
				$$$FSLog("Using introspection token object for validation")
				$$$FSLog("Introspection token aud=" _ $$$dynPropToString(introJWTObj.aud))
				Set ..%LastIntrospectionTime = ..TimeInSeconds($ztimestamp, 0)
				
			} Else {
				$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr","TokenIntrospectionInactive"))
			}
		
		} Else {
			// Success status without returned token is invalid.
			$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr","TokenIntrospectionNoToken"))
		}
		
	} Else {
		// Error code 8876 is $$$OAuth2NoEndpoint in %SYS. The lack of
		// an introspection endpoint is not considered fatal here. The
		// token obtained via ValidateJWT() will be used as a fallback.
		If $System.Status.Equals(introStatus, 8876) {
			Set ..%HasIntrospectionEP = 0
		} Else {
			$$$HttpOnlyThrowLog(401, $SYSTEM.Status.GetErrorText(introStatus))
        }
	}
	
	$$$FSLog("HasIntrospectionEP=" _ ..%HasIntrospectionEP)
	
	$$$FSLog("AlreadyValidated=" _ ..#AlreadyValidated)
	
    // *** IL PCM ***
    // Changed the OR (||) in the IF below to AND (&&) that if the introJWTObj exists (really the plain JSON itself, not a JWT) we don't need to Validate a JWT
    //-------------------------------------------

	// If introspection failed but allowed execution to continue, then
	// use ValidateJWT() to get an object from the token string.
	// If introspection succeeded and the token was not yet validated
	// via ValidateJWT(), then call ValidateJWT().
	If ('..#AlreadyValidated) && ('$IsObject(introJWTObj)) {
		// ValidateJWT() verifies that the token is sensical as a JWT, is not expired,
		// came from the correct issuer, along with other vital information.
		Set tReturn = ##class(%SYS.OAuth2.Validation).ValidateJWT(..%OAuthClient, ..%TokenString, "", "", .JWTObj, .securityParams, .tSC)
		
		If $$$ISERR(tSC)  {
			$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr","ValidateJWTFail",$system.Status.GetErrorText(tSC)))
		}
		
		// If a token object was not obtained via introspection, then set
		// ..%TokenObject to the object obtained from ValidateJWT().
		If '$IsObject(introJWTObj) {
			Set ..%TokenObject = JWTObj
			$$$FSLog("Using ValidateJWT() token object for validation")
			$$$FSLog("ValidateJWT() token aud=" _ $$$dynPropToString(JWTObj.aud))
		}
	}
	
	If '..#AlreadyValidated {
		
        // *** IL PCM ***
        // Since we didn't call ValidateJWT above then the securityParams won't exist, so skipping the next IF
        //-------------------------------------------    

		// Ensure that a JWT is signed. If ..#AlreadyValidated is 0,
		// then securityParams should have been set by ValidateJWT().
		/*If '$Data(securityParams("sigalg"))#2 {
			$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr","TokenNotSigned"))
		}*/
		
		// Validate the audience.
		If '..ValidateAudience() {
			Set audList = [(..%BaseURL)]
			For i = 1:1:..%Audiences.Count() {
				Do audList.%Push(..%Audiences.GetAt(i))
			}
			$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr", "TokenAudFail", audList.%ToJSON()))
		}
		
		// Validate the sub.
		If '..ValidateSub() {
			$$$HttpOnlyThrowLog(401, $$$FormatMsg("HSFHIRErr","TokenSubFail"))
		}
	}
	
	Do ..SetScopes()
	
	Do ..SetContextValues()
	
	Do ..VerifyScopesAndContext()
	
	$$$FSLog("Access token PASSED validation by " _ $$$CurrentMethod)
	
	Return
}

}
