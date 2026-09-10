import React, {

    useEffect,

    useState

} from "react";


import {

    getNotifications,

    markNotificationRead

} from "../../api/alertApi";


import "./Notification.css";





function NotificationBell(){



    const [open,setOpen] = useState(false);



    const [notifications,setNotifications] =

        useState([]);




    const [loading,setLoading] =

        useState(false);





    // ===============================
    // LOAD NOTIFICATIONS
    // ===============================


    useEffect(()=>{


        loadNotifications();


    },[]);







    const loadNotifications = async()=>{


        try{


            setLoading(true);



            const response =

                await getNotifications();





            console.log(
                "NOTIFICATION RESPONSE:",
                response.data
            );






            /*
            Backend response:

            {
                success:true,
                notifications:[]
            }

            */



            const data =

                response.data;



            if(Array.isArray(data)){


                setNotifications(data);


            }


            else if(

                Array.isArray(
                    data.notifications
                )

            ){


                setNotifications(

                    data.notifications

                );


            }


            else{


                setNotifications([]);


            }





        }


        catch(error){


            console.error(

                "NOTIFICATION ERROR:",

                error.response?.data
                ||
                error.message

            );



            setNotifications([]);


        }


        finally{


            setLoading(false);


        }


    };









    // ===============================
    // MARK READ
    // ===============================


    const handleRead = async(id)=>{


        try{


            await markNotificationRead(id);




            setNotifications(

                previous =>

                previous.map(item =>


                    item.id === id

                    ?

                    {

                        ...item,

                        is_read:true

                    }


                    :

                    item


                )


            );



        }


        catch(error){


            console.error(

                "MARK READ ERROR:",

                error

            );


        }


    };









    const unreadCount =

        notifications.filter(

            item =>

            !item.is_read

        ).length;









return (



<div className="notification-wrapper">






<button


className="notification-button"


onClick={()=>setOpen(!open)}


>


<i className="bi bi-bell"></i>





{

unreadCount > 0 &&


<span className="notification-count">


{unreadCount}


</span>


}





</button>








{

open &&



<div className="notification-dropdown">






<div className="notification-header">


<h3>

Notifications

</h3>


</div>









{

loading ?



<p className="notification-empty">

Loading...

</p>





:

notifications.length > 0 ?





notifications.map(

notification => (



<div


key={notification.id}


className={


notification.is_read


?

"notification-item read"


:

"notification-item"


}



onClick={()=>


handleRead(

notification.id

)


}


>





<h4>

{

notification.title

||

"Notification"

}

</h4>





<p>

{

notification.message

||

"No message"

}

</p>






<small>

{

notification.created_at

||

""

}

</small>





</div>



)


)






:



<p className="notification-empty">

No notifications

</p>




}





</div>



}





</div>


);


}



export default NotificationBell;