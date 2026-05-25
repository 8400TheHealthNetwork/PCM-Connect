Include HS.FHIRServer
Class PCMHack.Util.Utils Extends
{


ClassMethod GetPatientResourceId(strategy As HS.FHIRServer.Storage.JsonAdvSQL.InteractionsStrategy, identifier As %String = "") As %String [ Language = objectscript ]
{
    set interactions = strategy.NewInteractionsInstance() 

    set resourceId=""
    #dim res as HS.FHIRServer.Util.SearchResult
    try {
        set param=##class(HS.FHIRServer.API.Data.QueryParameters).CreateFromQueryString("identifier="_identifier,interactions.schema,"Patient")
        
        set res=interactions.Search("Patient","","",param)
        $$$FSLog("search status = "_res.SearchStatus)
        if res.%Next() {
            $$$FSLog("Found: "_res.%Get("Key"))
            set resourceId=res.%Get("ResourceId")
        }
    }
    catch ex {
        throw ex
    } 
    return resourceId
}






ClassMethod Test(iden As %String = "http://fhir.health.gov.il/identifier/il-national-id|000000018") 
{
    set strategy = ##class(HS.FHIRServer.Storage.JsonAdvSQL.InteractionsStrategy).GetStrategyForEndpoint("/csp/healthshare/teaminternal/fhir/r4")
    w ..GetPatientResourceId(strategy,iden)
}
}
