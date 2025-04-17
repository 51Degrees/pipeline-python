# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2025 51 Degrees Mobile Experts Limited, Davidson House,
# Forbury Square, Reading, Berkshire, United Kingdom RG1 3EU.
#
# This Original Work is licensed under the European Union Public Licence
# (EUPL) v.1.2 and is subject to its terms as set out below.
#
# If a copy of the EUPL was not distributed with this file, You can obtain
# one at https://opensource.org/licenses/EUPL-1.2.
#
# The 'Compatible Licences' set out in the Appendix to the EUPL (as may be
# amended by the European Commission) shall be deemed incompatible for
# the purposes of the Work and the provisions of the compatibility
# clause in Article 5 of the EUPL shall not apply.
#
# If using the Work as, or as part of, a network application, by
# including the attribution notice(s) required under Article 5 of the EUPL
# in the end user terms of the application under an appropriate heading,
# such notice(s) shall fulfill the requirements of that article.
# *********************************************************************


## @example client_side_evidence_custom_flow_element.py
# This example demonstrates the creation of a custom flow element. In this case 
# the flowElement takes the results of a client side form collecting 
# date of birth, setting this as evidence on a flowdata object to calculate 
# a person's starsign. The flowElement also serves additional JavaScript 
# which gets a user's geolocation and saves the latitude as a cookie. 
# This latitude is also then passed in to the flowdata to calculate if 
# a person is in the northern or southern hemispheres.

from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder
from fiftyone_pipeline_core.web import webevidence
from fiftyone_pipeline_core.basiclist_evidence_keyfilter import BasicListEvidenceKeyFilter
from fiftyone_pipeline_core.flowelement import FlowElement
from fiftyone_pipeline_core.elementdata_dictionary import ElementDataDictionary

import json

# Function to get star sign from month and day
def getStarSign(month, day):

    if (month == 1 and day <= 20) or (month == 12 and day >= 22):
        return "capricorn"

    elif (month == 1 and day >= 21) or (month == 2 and day <= 18):
        return "aquarius"
        
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return "pisces"

    elif (month == 3 and day >= 21) or (month == 4 and day <= 20):
        return "aries"

    elif (month == 4 and day >= 21) or (month == 5 and day <= 20):
        return "taurus"

    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "gemini"

    elif (month == 6 and day >= 22) or (month == 7 and day <= 22):
        return "cancer"

    elif (month == 7 and day >= 23) or (month == 8 and day <= 23):
        return "leo"

    elif (month == 8 and day >= 24) or (month == 9 and day <= 23):
        return "virgo"

    elif (month == 9 and day >= 24) or (month == 10 and day <= 23):
        return "libra"

    elif (month == 10 and day >= 24) or (month == 11 and day <= 22):
        return "scorpio"

    elif (month == 11 and day >= 23) or (month == 12 and day <= 21):
        return "sagittarius"


class AstrologyFlowElement(FlowElement):

    def __init__(self):

        super(AstrologyFlowElement, self).__init__()

        self.datakey = "astrology"

        # set the FLowElement's properties

        self.properties = {
            "hemisphere": {
                "type": 'string',
                "description": "the user's hemisphere"
            },
            "starSign": {
                "type": 'string',
                "description": "the user's starsign"
            },
            "getLatitude": {
                "type": 'javascript',
                "description": "JavaScript used to get a user's latitude"
            }
        }
    

    # The process_internal function is the core working of a flowElement. 
    # It takes FlowData, reads evidence and returns data.
    def process_internal(self, flowdata):

        result = {}
        
        # Get the date of birth from the query string (submitted through 
        # a form on the client side)
        dateOfBirth = flowdata.evidence.get("query.dateOfBirth")
        
        if dateOfBirth:

            dateOfBirth = dateOfBirth.split('-') 

            month = int(dateOfBirth[1]) 
            day = int(dateOfBirth[2])

            result["starSign"] = getStarSign(month, day)

      
        # Serve some JavaScript to the user that will be used to save 
        # a cookie with the user's latitude in it
        result["getLatitude"] = """
        navigator.geolocation.getCurrentPosition(function(position) {
            document.cookie = \"latitude=\" + position.coords.latitude;
            console.log(document.cookie)
            loadHemisphere();
        });
        """

        # Get the latitude from the above cookie
        latitude = flowdata.evidence.get("cookie.latitude")

        # Calculate the hemisphere
        if latitude:

            result["hemisphere"] = "Northern" if float(latitude) > 0 else "Southern"
          
        data = ElementDataDictionary(self, result)

        flowdata.set_element_data(data)

    def get_evidence_key_filter(self):
        """
        get_evidence_key_filter - A filter (in this case a basic list) stating which evidence 
        the flowElement is interested in
        """
        return  BasicListEvidenceKeyFilter(["cookie.latitude", "query.dateOfBirth"])


# Add some callback settings for the page to make a request with extra evidence from the client side, in this case the Flask /json route we have made below

javascript_builder_settings = {
    "endpoint": "/json"
}

# Make the pipeline and add the element we want to it

myPipeline = (PipelineBuilder({"javascript_builder_settings": javascript_builder_settings})).add(AstrologyFlowElement()).build()

from flask import Flask, request

app = Flask(__name__)

# Make a route that returns back JSON encded properties for client side scripts to pick up

@app.route('/json', methods=['POST'])
def jsonroute():

    # Create the flowdata object for the JSON route
    flowdata = myPipeline.create_flowdata()

    # Add any information from the request (headers, cookies and additional 
    # client side provided information)

    flowdata.evidence.add_from_dict(webevidence(request))

    # Process the flowdata

    flowdata.process()

    # Return the JSON from the JSONBundler engine

    return json.dumps(flowdata.jsonbundler.json)
    

@app.route('/')
def server():
    
    flowdata = myPipeline.create_flowdata()

    # Add any information from the request (headers, cookies and additional 
    # client side provided information)

    flowdata.evidence.add_from_dict(webevidence(request))

    # Process the flowdata

    flowdata.process()

    # Generate the HTML for the form that gets a user's starsign 

    output = ""

    output += "<h1>Starsign</h1>"

    output += "<form><label for='dateOfBirth'>Date of birth</label><input type='date' name='dateOfBirth' id='dateOfBirth'><input type='submit'></form>"

    ## Add the results if they're available

    if (flowdata.astrology.starSign):
        output += "<p>Your starsign is " + flowdata.astrology.starSign + "</p>"

    output += "<div id='hemispheretext'>"

    if (flowdata.astrology.hemisphere):
        output += "<p>Look at the " + flowdata.astrology.hemisphere + " hemisphere stars tonight!</p>"

    output += "</div>"

    output += "<script>"

    ## This function will fire when the JSON data object is updated
    ## with information from the server.
    ## The sequence is:
    ## 1. Response contains JavaScript property 'getLatitude' that gets executed on the client
    ## 2. This triggers another call to the webserver that passes the location as evidence
    ## 3. The web server responds with new JSON data that contains the hemisphere based on the location.
    ## 4. The JavaScript integrates the new JSON data and fires the onChange callback below.

    output += flowdata.javascriptbuilder.javascript

    output += """
        const loadHemisphere = function() {
            fod.complete(function (data) {  
                if(data.astrology.hemisphere) {          
                    var para = document.createElement("p");
                    var text = document.createTextNode("Look at the " + 
                        data.astrology.hemisphere + " hemisphere stars tonight");
                    para.appendChild(text);

                    var element = document.getElementById("hemispheretext");
                    var child = element.lastElementChild;  
                    while (child) { 
                        element.removeChild(child); 
                        child = element.lastElementChild; 
                    } 
                    element.appendChild(para);
                }
            })
            };
            
            """

    output += "</script>"

    # Return the full output to the page

    return output
