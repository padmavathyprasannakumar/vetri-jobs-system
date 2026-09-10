import React, {

    useEffect,

    useState

} from "react";


import {

    FaBuilding,

    FaGlobe,

    FaPhone,

    FaEnvelope,

    FaMapMarkerAlt,

    FaUpload,

    FaSave,

    FaIndustry,

    FaInfoCircle,

    FaAddressCard,

    FaShareAlt,

    FaUsers,

    FaLinkedin,

    FaTwitter,

    FaFacebook,
    FaEdit,

    FaInstagram,

    FaPlus,

    FaTrash

} from "react-icons/fa";


import {

    getCompanyProfile,

    updateCompanyProfile,

    uploadCompanyLogo

} from "../../../api/companyApi";


import Avatar from "../../../components/Avatar/Avatar";

import "./CompanyProfile.css";




const TABS = [

    { key:"info", label:"Company Information", icon:<FaBuilding/> },

    { key:"about", label:"About Company", icon:<FaInfoCircle/> },

    { key:"contact", label:"Contact Information", icon:<FaAddressCard/> },

    { key:"social", label:"Social Media", icon:<FaShareAlt/> },

    { key:"team", label:"Team Members", icon:<FaUsers/> },

];




const EMPTY_PROFILE = {

    company_name:"",

    industry:"",

    company_size:"",

    founded_year:"",

    website:"",

    tagline:"",

    description:"",

    vision:"",

    mission:"",

    contact_email:"",

    phone:"",

    address:"",

    linkedin:"",

    twitter:"",

    facebook:"",

    instagram:"",

    team_members:[],

};




const CompanyProfile = ()=>{



const [profile,setProfile]=useState(EMPTY_PROFILE);



const [logo,setLogo]=useState(null);



const [loading,setLoading]=useState(true);



const [saving,setSaving]=useState(false);

const [isEditing,setIsEditing]=useState(false);



const [message,setMessage]=useState("");



const [activeTab,setActiveTab]=useState("info");






useEffect(()=>{


loadProfile();


},[]);






// =====================================
// LOAD PROFILE
// =====================================


const loadProfile=async()=>{


try{


const response =

await getCompanyProfile();



setProfile({

...EMPTY_PROFILE,

...response.data,

team_members: response.data?.team_members || [],

});



}

catch(error){


console.log(error);


}

finally{


setLoading(false);


}



};







const handleChange=(e)=>{


setProfile({


...profile,


[e.target.name]:

e.target.value



});


};







// =====================================
// TEAM MEMBERS
// =====================================


const addTeamMember=()=>{

setProfile({

...profile,

team_members:[

...(profile.team_members||[]),

{ name:"", role:"", email:"" }

]

});

};



const updateTeamMember=(index,field,value)=>{

const members = [...(profile.team_members||[])];

members[index] = { ...members[index], [field]:value };

setProfile({ ...profile, team_members: members });

};



const removeTeamMember=(index)=>{

const members = [...(profile.team_members||[])];

members.splice(index,1);

setProfile({ ...profile, team_members: members });

};







// =====================================
// UPDATE PROFILE
// =====================================


const handleUpdate=async()=>{


try{


setSaving(true);



await updateCompanyProfile(

profile

);



setMessage(

"Company profile updated successfully"

);


setIsEditing(false);



}

catch(error){


console.log(error);



setMessage(

"Profile update failed"

);



}

finally{


setSaving(false);


}



};







// =====================================
// LOGO UPLOAD
// =====================================


const handleLogoChange=(e)=>{

setLogo(e.target.files[0]);

};



const handleLogoUpload=async()=>{


if(!logo) return;


try{


const formData = new FormData();

formData.append("logo", logo);


await uploadCompanyLogo(formData);


setMessage("Logo updated successfully");


loadProfile();


}

catch(error){


console.log(error);


setMessage("Logo upload failed");


}


};








if(loading){


return(


<div className="company-loading">

<div className="spinner-border"></div>

<p>Loading company profile...</p>

</div>


);


}








return(



<div className="company-profile-page">




{/* HEADER BANNER */}


<div className="profile-banner">


<div className="profile-banner-icon">

<FaBuilding/>

</div>


<div>

<h1>Company Profile</h1>

<p>Complete your company information to attract the best candidates.</p>

</div>


{
!isEditing &&

<button

className="edit-profile-btn"

onClick={()=>setIsEditing(true)}

>

<FaEdit/> Update Profile

</button>
}


</div>




{
message &&

<div className="profile-message">{message}</div>

}




{/* TABS */}


<div className="profile-tabs">


{
TABS.map(tab=>(

<button

key={tab.key}

className={activeTab===tab.key ? "profile-tab active" : "profile-tab"}

onClick={()=>setActiveTab(tab.key)}

>

{tab.icon} {tab.label}

</button>

))
}


</div>




<div className="profile-form-card">


<fieldset disabled={!isEditing} className="profile-fieldset">




{/* =============== COMPANY INFORMATION =============== */}

{
activeTab==="info" &&

<div className="profile-section">


<h2><FaBuilding/> Company Information</h2>


<div className="profile-logo-row">

<div className="profile-logo-preview">

{
profile.logo ?
<img src={profile.logo} alt="Company logo"/>
:
<Avatar name={profile.company_name} size={80}/>
}

</div>


<div>

<input type="file" accept="image/*" onChange={handleLogoChange}/>

<button className="logo-upload-btn" onClick={handleLogoUpload}>

<FaUpload/> Upload Logo

</button>

</div>

</div>



<div className="form-grid">


<div className="form-field">

<label>Company Name *</label>

<input

name="company_name"

value={profile.company_name||""}

onChange={handleChange}

placeholder="e.g. TechNova Solutions"

/>

</div>


<div className="form-field">

<label>Industry *</label>

<input

name="industry"

value={profile.industry||""}

onChange={handleChange}

placeholder="e.g. Information Technology"

/>

</div>


<div className="form-field">

<label>Company Size</label>

<select

name="company_size"

value={profile.company_size||""}

onChange={handleChange}

>

<option value="">Select size</option>

<option value="1-10 Employees">1-10 Employees</option>

<option value="11-50 Employees">11-50 Employees</option>

<option value="51-200 Employees">51-200 Employees</option>

<option value="201-500 Employees">201-500 Employees</option>

<option value="500+ Employees">500+ Employees</option>

</select>

</div>


<div className="form-field">

<label>Founded Year</label>

<input

name="founded_year"

value={profile.founded_year||""}

onChange={handleChange}

placeholder="e.g. 2018"

/>

</div>


<div className="form-field">

<label><FaGlobe/> Website</label>

<input

name="website"

value={profile.website||""}

onChange={handleChange}

placeholder="https://yourcompany.com"

/>

</div>


</div>


</div>

}




{/* =============== ABOUT COMPANY =============== */}

{
activeTab==="about" &&

<div className="profile-section">


<h2><FaInfoCircle/> About Company</h2>


<div className="form-field full">

<label>Tagline / Company Motto</label>

<input

name="tagline"

value={profile.tagline||""}

onChange={handleChange}

placeholder="e.g. Innovating Tomorrow, Today."

/>

</div>


<div className="form-field full">

<label>Company Description *</label>

<textarea

name="description"

rows={3}

value={profile.description||""}

onChange={handleChange}

placeholder="Tell candidates what your company does..."

/>

</div>


<div className="form-field full">

<label>Company Vision</label>

<textarea

name="vision"

rows={2}

value={profile.vision||""}

onChange={handleChange}

placeholder="Your long term vision..."

/>

</div>


<div className="form-field full">

<label>Company Mission</label>

<textarea

name="mission"

rows={2}

value={profile.mission||""}

onChange={handleChange}

placeholder="Your mission statement..."

/>

</div>


</div>

}




{/* =============== CONTACT INFORMATION =============== */}

{
activeTab==="contact" &&

<div className="profile-section">


<h2><FaAddressCard/> Contact Information</h2>


<div className="form-grid">


<div className="form-field">

<label><FaEnvelope/> Email *</label>

<input

name="contact_email"

value={profile.contact_email||""}

onChange={handleChange}

placeholder="hr@yourcompany.com"

/>

</div>


<div className="form-field">

<label><FaPhone/> Phone Number *</label>

<input

name="phone"

value={profile.phone||""}

onChange={handleChange}

placeholder="+1 (555) 123-4567"

/>

</div>


</div>


<div className="form-field full">

<label><FaMapMarkerAlt/> Address *</label>

<textarea

name="address"

rows={2}

value={profile.address||""}

onChange={handleChange}

placeholder="Street, City, State, ZIP"

/>

</div>


</div>

}




{/* =============== SOCIAL MEDIA =============== */}

{
activeTab==="social" &&

<div className="profile-section">


<h2><FaShareAlt/> Social Media</h2>


<div className="form-grid">


<div className="form-field">

<label><FaLinkedin/> LinkedIn</label>

<input

name="linkedin"

value={profile.linkedin||""}

onChange={handleChange}

placeholder="https://linkedin.com/company/..."

/>

</div>


<div className="form-field">

<label><FaTwitter/> Twitter / X</label>

<input

name="twitter"

value={profile.twitter||""}

onChange={handleChange}

placeholder="https://twitter.com/..."

/>

</div>


<div className="form-field">

<label><FaFacebook/> Facebook</label>

<input

name="facebook"

value={profile.facebook||""}

onChange={handleChange}

placeholder="https://facebook.com/..."

/>

</div>


<div className="form-field">

<label><FaInstagram/> Instagram</label>

<input

name="instagram"

value={profile.instagram||""}

onChange={handleChange}

placeholder="https://instagram.com/..."

/>

</div>


</div>


</div>

}




{/* =============== TEAM MEMBERS =============== */}

{
activeTab==="team" &&

<div className="profile-section">


<h2><FaUsers/> Team Members</h2>


{
(profile.team_members||[]).map((member,index)=>(

<div className="team-member-row" key={index}>


<input

placeholder="Name"

value={member.name||""}

onChange={(e)=>updateTeamMember(index,"name",e.target.value)}

/>


<input

placeholder="Role"

value={member.role||""}

onChange={(e)=>updateTeamMember(index,"role",e.target.value)}

/>


<input

placeholder="Email"

value={member.email||""}

onChange={(e)=>updateTeamMember(index,"email",e.target.value)}

/>


<button

className="remove-member-btn"

onClick={()=>removeTeamMember(index)}

>

<FaTrash/>

</button>


</div>

))
}


<button className="add-member-btn" onClick={addTeamMember}>

<FaPlus/> Add Team Member

</button>


</div>

}




{/* SAVE ROW */}


</fieldset>


{
isEditing &&

<div className="profile-save-row">


<button

className="cancel-btn"

onClick={()=>{

loadProfile();

setIsEditing(false);

}}

>

Cancel

</button>


<button

className="save-btn"

onClick={handleUpdate}

disabled={saving}

>

<FaSave/> {saving ? "Saving..." : "Save Changes"}

</button>


</div>
}




</div>




</div>


);



};




export default CompanyProfile;
