export const API=import.meta.env.VITE_API_URL||'http://localhost:8000/api/v1';
export const WS=import.meta.env.VITE_WS_URL||'ws://localhost:8000/api/v1/ws';
export async function request<T>(path:string,options:RequestInit={},token?:string):Promise<T>{
 const response=await fetch(`${API}${path}`,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{ }),...options.headers}});
 if(!response.ok){let detail=`Request failed (${response.status})`;try{const body=await response.json();detail=body.detail||detail}catch{detail=`Request failed (${response.status})`}throw new Error(detail)}return response.json();
}
