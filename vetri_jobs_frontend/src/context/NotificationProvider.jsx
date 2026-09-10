import React, {

    createContext,

    useContext,

    useState,

    useEffect,

    useCallback

} from "react";



import {

    getNotifications,

    markNotificationRead

} from "../api/alertApi";






// =====================================================
// CREATE CONTEXT
// =====================================================


const NotificationContext = createContext(null);








// =====================================================
// CUSTOM HOOK
// =====================================================


export const useNotification = ()=>{


    const context = useContext(

        NotificationContext

    );



    if(!context){


        throw new Error(

            "useNotification must be used inside NotificationProvider"

        );


    }



    return context;


};









// =====================================================
// PROVIDER
// =====================================================


export function NotificationProvider({children}){



const [notifications,setNotifications]=useState([]);



const [unreadCount,setUnreadCount]=useState(0);



const [loading,setLoading]=useState(false);



const [error,setError]=useState(null);









// =====================================================
// CALCULATE UNREAD
// =====================================================


const calculateUnread=(data)=>{


    return data.filter(

        item =>

        !item.is_read

    )

    .length;


};









// =====================================================
// LOAD NOTIFICATIONS
// =====================================================


const loadNotifications = useCallback(async()=>{


try{


    setLoading(true);



    const response = await getNotifications();




    const data =


    Array.isArray(response.data)

    ?

    response.data

    :

    response.data.results || [];






    setNotifications(

        data

    );





    setUnreadCount(

        calculateUnread(data)

    );



    setError(null);



}



catch(err){



    console.error(

        "NOTIFICATION LOAD ERROR",

        err

    );



    setError(

        "Unable to load notifications"

    );


}



finally{


    setLoading(false);


}



},[]);









// =====================================================
// INITIAL LOAD
// =====================================================


useEffect(()=>{


    loadNotifications();



},[loadNotifications]);









// =====================================================
// MARK READ
// =====================================================


const markAsRead = async(id)=>{


try{


    await markNotificationRead(id);




    setNotifications(

        previous =>


        previous.map(item=>



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





    setUnreadCount(

        previous =>


        previous > 0

        ?

        previous-1

        :

        0


    );





}



catch(error){


    console.error(

        "MARK READ ERROR",

        error

    );


}



};









// =====================================================
// ADD LOCAL NOTIFICATION
// =====================================================


const addNotification=(notification)=>{


const newNotification={


    id:

    Date.now(),



    is_read:false,



    created_at:

    new Date(),



    ...notification



};





setNotifications(

    previous=>[

        newNotification,

        ...previous

    ]

);



setUnreadCount(

    previous=>previous+1

);



};









// =====================================================
// REMOVE NOTIFICATION
// =====================================================


const removeNotification=(id)=>{



setNotifications(

    previous =>


    previous.filter(

        item =>

        item.id !== id

    )


);




};









// =====================================================
// CLEAR ALL
// =====================================================


const clearNotifications=()=>{


setNotifications([]);



setUnreadCount(0);



};









// =====================================================
// REFRESH TIMER
// =====================================================


const refreshNotifications=()=>{


    loadNotifications();


};









// =====================================================
// PROVIDER VALUE
// =====================================================


const value={



    notifications,


    unreadCount,


    loading,


    error,



    loadNotifications,


    refreshNotifications,



    markAsRead,


    addNotification,


    removeNotification,


    clearNotifications,


    setNotifications



};









return (


<NotificationContext.Provider


value={value}


>


{children}


</NotificationContext.Provider>


);



}