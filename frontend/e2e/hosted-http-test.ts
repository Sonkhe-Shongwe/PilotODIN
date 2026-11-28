import {test as base} from '@playwright/test';

// Only the nonsecret marker and same-origin witness appear in direct fixture
// HTTP traces; the Vite server adds the capability on the private upstream.
export const test=base.extend({
 request:async({playwright},use)=>{
   const context=await playwright.request.newContext({
     baseURL:'http://127.0.0.1:5178',
     extraHTTPHeaders:{'X-PilotODIN-Dev-Request':'1','Origin':'http://127.0.0.1:5178'}
   });
   try{await use(context);}finally{await context.dispose();}
 }
});
