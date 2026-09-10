import React, {

    useEffect,

    useState

} from "react";


import api from "../../../api/axios";


import {

    FaBell,

    FaCheck,

    FaTrash

} from "react-icons/fa";


import "./CompanyNotifications.css";




const CompanyNotifications = ()=>{


const [notifications,setNotifications] = useState([]);

const [loading,setLoading] = useState(true);




const load = ()=>{

api.get("/notifications/")

.then(res=>setNotifications(res.data || []))

.catch(err=>console.log("COMPANY NOTIFICATIONS ERROR", err))

.finally(()=>setLoading(false));

};


useEffect(()=>{

load();

},[]);




const handleMarkRead = async(id)=>{

try{

await api.patch("/notifications/" + id + "/read/");

setNotifications(prev=>prev.map(n=>n.id===id ? {...n, is_read:true} : n));

}
catch(error){

console.log("MARK READ ERROR", error);

}

};


const handleDelete = async(id)=>{

try{

await api.delete("/notifications/" + id + "/delete/");

setNotifications(prev=>prev.filter(n=>n.id!==id));

}
catch(error){

console.log("DELETE ERROR", error);

}

};


const handleMarkAllRead = async()=>{

try{

await api.patch("/notifications/mark-all-read/");

setNotifications(prev=>prev.map(n=>({...n, is_read:true})));

}
catch(error){

console.log("MARK ALL READ ERROR", error);

}

};




return(


<div className="company-notifications-page">


<div className="cn-header">

<div className="cn-header-icon"><FaBell/></div>

<div>

<h1>Notifications</h1>

<p>Stay updated on candidates, applications and interviews</p>

</div>

<button className="cn-mark-all-btn" onClick={handleMarkAllRead}>

<FaCheck/> Mark All as Read

</button>

</div>


<div className="cn-list">

{
loading ? (

<p className="cn-empty">Loading notifications...</p>

) : notifications.length > 0 ? (

notifications.map(n=>(

<div className={"cn-card " + (n.is_read ? "read" : "unread")} key={n.id}>

<div className="cn-card-body">

<p>{n.message}</p>

<span>{n.created_at ? new Date(n.created_at).toLocaleString() : ""}</span>

</div>

<div className="cn-card-actions">

{
!n.is_read &&

<button onClick={()=>handleMarkRead(n.id)} title="Mark as read"><FaCheck/></button>
}

<button onClick={()=>handleDelete(n.id)} title="Delete"><FaTrash/></button>

</div>

</div>

))

) : (

<p className="cn-empty">No notifications yet</p>

)
}

</div>


</div>


);



};




export default CompanyNotifications;
