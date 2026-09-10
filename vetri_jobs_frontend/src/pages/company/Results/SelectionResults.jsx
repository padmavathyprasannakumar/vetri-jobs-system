import React, {

    useEffect,

    useState

} from "react";


import {

    getSelectionResults,

    updateCandidateResult

} from "../../../api/companyApi";


import {

    FaCheckCircle,

    FaTimesCircle,

    FaClock,

    FaUserGraduate

} from "react-icons/fa";


import "./Results.css";






const SelectionResults=()=>{



const [results,setResults]=useState([]);


const [loading,setLoading]=useState(true);





useEffect(()=>{


loadResults();


},[]);







const loadResults=async()=>{


try{


const response = await getSelectionResults();



setResults(

response.data

);



}


catch(error){


console.log(

"RESULT LOAD ERROR",

error

);


}


finally{


setLoading(false);


}


};









const changeStatus=async(id,status)=>{


try{


await updateCandidateResult(

id,

{

status:status

}

);





loadResults();



}

catch(error){


console.log(error);


}



};










if(loading){


return(

<div className="result-loading">

Loading selection results...

</div>

);


}










return(


<div className="selection-results">





<h1>

Candidate Selection Results

</h1>



<p>

Review interview outcome and update candidate status.

</p>







<div className="result-table">



<div className="result-header">


<span>

Candidate

</span>


<span>

Job

</span>


<span>

Status

</span>


<span>

Action

</span>



</div>










{

results.length===0 ?


<div className="empty-result">

No completed interviews found.

</div>


:



results.map(candidate=>(



<div

className="result-row"

key={candidate.id}

>



<div className="candidate-name">


<FaUserGraduate/>


<div>


<h4>

{candidate.name}

</h4>


<p>

{candidate.email}

</p>


</div>


</div>





<div>


{candidate.job_title}


</div>






<div>


<span

className={

`status ${

candidate.status

}`

}

>

{

candidate.status

}


</span>


</div>






<div className="result-actions">



<button


className="select-btn"


onClick={()=>


changeStatus(

candidate.id,

"selected"

)


}


>


<FaCheckCircle/>

Select

</button>






<button


className="hold-btn"


onClick={()=>


changeStatus(

candidate.id,

"hold"

)


}


>


<FaClock/>

Hold

</button>






<button


className="reject-btn"


onClick={()=>


changeStatus(

candidate.id,

"rejected"

)


}


>


<FaTimesCircle/>

Reject

</button>



</div>






</div>



))


}





</div>







</div>



);


};



export default SelectionResults;