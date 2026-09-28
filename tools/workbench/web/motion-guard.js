// One guard is shared by asset/clip/character/rig/navigation/refresh/export paths.
export function draftGuard(confirm){
  let current;
  return {
    attach(value){current=value;},
    pending(){return !!current?.pending();},
    async allow(){
      if(current?.busy())return false;
      if(!current?.pending())return true;
      if(!await confirm())return false;
      current.discard();return true;
    }
  };
}
