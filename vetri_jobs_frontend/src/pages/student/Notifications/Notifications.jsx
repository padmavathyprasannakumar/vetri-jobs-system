import React,{

useEffect,

useState

} from "react";



import {

getStudentNotifications,

markNotificationRead,

deleteNotification,

markAllNotificationsRead

} from "../../../api/studentApi";


import { useNotification } from "../../../context/NotificationProvider";



import {

FaBell,

FaBriefcase,

FaCalendarCheck,

FaBuilding,

FaCheckCircle,

FaTimesCircle,

FaClock,

FaTrash,

FaCheck,

FaArrowRight

} from "react-icons/fa";



import {

useNavigate

} from "react-router-dom";



import "./Notifications.css";









const Notifications=()=>{



const navigate=useNavigate();



const [notifications,setNotifications]=useState([]);

const { refreshNotifications } = useNotification();


const handleMarkRead = async(notificationId)=>{

try{

await markNotificationRead(notificationId);

setNotifications(prev=>prev.map(n=>

n.id===notificationId ? {...n, is_read:true} : n

));

refreshNotifications();

}
catch(error){

console.log("MARK READ ERROR", error);

}

};


const handleDeleteNotification = async(notificationId)=>{

try{

await deleteNotification(notificationId);

setNotifications(prev=>prev.filter(n=>n.id!==notificationId));

refreshNotifications();

}
catch(error){

console.log("DELETE NOTIFICATION ERROR", error);

}

};


const handleMarkAllRead = async()=>{

try{

await markAllNotificationsRead();

setNotifications(prev=>prev.map(n=>({...n, is_read:true})));

refreshNotifications();

}
catch(error){

console.log("MARK ALL READ ERROR", error);

}

};



const [loading,setLoading]=useState(true);


const [error,setError]=useState("");









// =====================================
// LOAD NOTIFICATIONS
// =====================================


useEffect(()=>{


loadNotifications();


},[]);









const loadNotifications=async()=>{


try{


const response=

await getStudentNotifications();



setNotifications(

response.data

);



}

catch(error){


console.log(

"NOTIFICATION ERROR",

error

);



setError(

"Unable to load notifications"

);



}

finally{


setLoading(false);


}



};











// =====================================
// ICON
// =====================================


const notificationIcon=(type)=>{


switch(

type?.toLowerCase()

){



case "application":


return <FaBriefcase/>;




case "interview":


return <FaCalendarCheck/>;




case "company":


return <FaBuilding/>;




case "success":


return <FaCheckCircle/>;




case "rejected":


return <FaTimesCircle/>;




default:


return <FaBell/>;



}



};











// =====================================
// CLASS
// =====================================


const notificationClass=(read)=>{


return read

?

"read"

:

"unread";


};













if(loading){


return(


<div className="notification-loading">


<div className="loader"></div>


<p>

Loading notifications...

</p>


</div>


);


}












return(



<div className="student-notifications">







{/* HEADER */}



<div className="notification-banner">



<div>


<h1>

Notifications

</h1>


<p>

Stay updated with your career activities

</p>



</div>

<button

className="notification-mark-all-btn"

onClick={handleMarkAllRead}

>

<FaCheck/> Mark All as Read

</button>







<div className="notification-icon">


<FaBell/>


</div>



</div>









{

error &&


<div className="notification-error">


{error}


</div>


}












<div className="notification-list">







{

notifications.length > 0



?



notifications.map(

(notification)=>(



<div

className={

`notification-card ${

notificationClass(

notification.is_read

)

}`

}

key={notification.id}


>









<div className="notification-left">



<div className="notification-type">


{

notificationIcon(

notification.type

)

}


</div>





<div className="notification-content">



<h3>


{

notification.title

||

"Notification"


}


</h3>





<p>


{

notification.message

||

"No message available"


}


</p>







<div className="notification-time">


<FaClock/>


{

notification.created_at

||

"Recently"


}



</div>







</div>



</div>









<div className="notification-action">



{

notification.action_url &&



<button


onClick={()=>navigate(

notification.action_url

)}


>


View


<FaArrowRight/>


</button>



}


{
!notification.is_read &&

<button

className="notification-mark-read-btn"

onClick={()=>handleMarkRead(notification.id)}

title="Mark as read"

>

<FaCheck/> Mark as read

</button>
}


<button

className="notification-delete-btn"

onClick={()=>handleDeleteNotification(notification.id)}

title="Delete"

>

<FaTrash/>

</button>


</div>









</div>



)


)



:





<div className="empty-notifications">



<FaBell/>


<h2>

No Notifications

</h2>



<p>

You will receive updates about jobs and applications here.

</p>


<button


onClick={()=>navigate("/student/jobs")}


>


Browse Jobs


</button>



</div>





}








</div>







</div>



);


};





export default Notifications;