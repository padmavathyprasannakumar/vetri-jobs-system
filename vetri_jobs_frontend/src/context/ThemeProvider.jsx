import React, {

    createContext,

    useContext,

    useEffect,

    useState

} from "react";




// =====================================================
// CREATE CONTEXT
// =====================================================


const ThemeContext = createContext(null);







// =====================================================
// CUSTOM HOOK
// =====================================================


export const useTheme = ()=>{


    const context = useContext(

        ThemeContext

    );



    if(!context){


        throw new Error(

            "useTheme must be used inside ThemeProvider"

        );


    }



    return context;


};









// =====================================================
// THEME PROVIDER
// =====================================================


export function ThemeProvider({children}){



// =====================================================
// GET INITIAL THEME
// =====================================================


const getInitialTheme=()=>{


    const savedTheme =

    localStorage.getItem(

        "theme"

    );



    if(savedTheme){


        return savedTheme;


    }






    // System preference


    const prefersDark =

    window.matchMedia &&

    window.matchMedia(

        "(prefers-color-scheme: dark)"

    )

    .matches;





    return prefersDark

    ?

    "dark"

    :

    "light";



};







const [theme,setTheme]=useState(

    getInitialTheme()

);








// =====================================================
// APPLY THEME
// =====================================================


useEffect(()=>{



    const root =

    document.documentElement;





    root.setAttribute(

        "data-theme",

        theme

    );





    localStorage.setItem(

        "theme",

        theme

    );





},[theme]);









// =====================================================
// CHANGE THEME
// =====================================================


const changeTheme=(newTheme)=>{



if(

    newTheme === "light"

    ||

    newTheme === "dark"

){


    setTheme(newTheme);


}



};









// =====================================================
// TOGGLE THEME
// =====================================================


const toggleTheme=()=>{


    setTheme(

        previous =>


        previous === "light"

        ?

        "dark"

        :

        "light"

    );


};









// =====================================================
// CHECK MODE
// =====================================================


const isDark =

theme === "dark";







const isLight =

theme === "light";









// =====================================================
// PROVIDER VALUE
// =====================================================


const value={



    theme,


    setTheme,


    changeTheme,


    toggleTheme,


    isDark,


    isLight



};








return (


<ThemeContext.Provider


value={value}


>


{children}


</ThemeContext.Provider>



);



}