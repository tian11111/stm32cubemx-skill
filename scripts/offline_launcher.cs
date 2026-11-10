using System;
using System.Text;
using System.ComponentModel;
using System.Runtime.InteropServices;
class OfflineLauncher {
 [StructLayout(LayoutKind.Sequential)] struct Caps { public IntPtr sid, caps; public uint count, reserved; }
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Startup { public int cb; public string reserved, desktop, title; public int x,y,xs,ys,xc,yc,fill,flags; public short show,reserved2; public IntPtr ptr, input, output, error; }
 [StructLayout(LayoutKind.Sequential)] struct StartupEx { public Startup startup; public IntPtr attrs; }
 [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process, thread; public uint pid, tid; }
 [StructLayout(LayoutKind.Sequential)] struct BasicLimit { public long perProcess, perJob; public uint flags; public UIntPtr min, max; public uint active; public UIntPtr affinity; public uint priority, scheduling; }
 [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong a,b,c,d,e,f; }
 [StructLayout(LayoutKind.Sequential)] struct ExtendedLimit { public BasicLimit basic; public IoCounters io; public UIntPtr processMemory, jobMemory, peakProcess, peakJob; }
 [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool ConvertStringSidToSid(string text,out IntPtr sid);
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr ptr);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attr,string name);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int cls,ref ExtendedLimit info,uint size);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool InitializeProcThreadAttributeList(IntPtr list,int count,int flags,ref IntPtr size);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool UpdateProcThreadAttribute(IntPtr list,uint flags,IntPtr attr,IntPtr value,IntPtr size,IntPtr prev,IntPtr ret);
 [DllImport("kernel32.dll")] static extern void DeleteProcThreadAttributeList(IntPtr list);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool CreateProcessW(string app,StringBuilder cmd,IntPtr pa,IntPtr ta,bool inherit,uint flags,IntPtr env,string dir,ref StartupEx startup,out ProcessInfo pi);
 [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr GetStdHandle(int n);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool DuplicateHandle(IntPtr src,IntPtr handle,IntPtr dst,out IntPtr copy,uint access,bool inherit,uint options);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int cls,IntPtr info,int size,out int needed);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr handle,uint ms);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr process,out uint code);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
 static void Check(bool result,string action) { if(!result) throw new Win32Exception(Marshal.GetLastWin32Error(),action); }
 static string Quote(string s) { var b=new StringBuilder("\""); int n=0; foreach(char c in s) { if(c=='\\') { n++; continue; } if(c=='\"') { b.Append('\\',n*2+1); b.Append(c); n=0; continue; } b.Append('\\',n); n=0; b.Append(c); } b.Append('\\',n*2); return b.Append('\"').ToString(); }
 static int Main(string[] args) {
  if(args.Length<2) { Console.Error.WriteLine("Usage: OfflineLauncher.exe <appcontainer-sid> <absolute-executable> [arguments...]"); return 255; }
  IntPtr sid=IntPtr.Zero,job=IntPtr.Zero,list=IntPtr.Zero,cap=IntPtr.Zero,jobptr=IntPtr.Zero,handleptr=IntPtr.Zero,token=IntPtr.Zero,buf=IntPtr.Zero; IntPtr[] std=new IntPtr[3]; bool initialized=false; ProcessInfo pi=new ProcessInfo();
  try {
   if(!System.IO.Path.IsPathRooted(args[1])) throw new Exception("Executable path must be absolute");
   Check(ConvertStringSidToSid(args[0],out sid),"ConvertStringSidToSid");
   job=CreateJobObject(IntPtr.Zero,null); Check(job!=IntPtr.Zero,"CreateJobObject"); ExtendedLimit limit=new ExtendedLimit(); limit.basic.flags=0x2000; Check(SetInformationJobObject(job,9,ref limit,(uint)Marshal.SizeOf(limit)),"SetInformationJobObject");
   for(int i=0;i<3;i++) { IntPtr h=GetStdHandle(-10-i); Check(h!=IntPtr.Zero && h!=new IntPtr(-1),"GetStdHandle"); Check(DuplicateHandle(GetCurrentProcess(),h,GetCurrentProcess(),out std[i],0,true,2),"DuplicateHandle"); }
   IntPtr size=IntPtr.Zero; InitializeProcThreadAttributeList(IntPtr.Zero,3,0,ref size); list=Marshal.AllocHGlobal(size); Check(InitializeProcThreadAttributeList(list,3,0,ref size),"InitializeProcThreadAttributeList"); initialized=true;
   Caps c=new Caps {sid=sid}; cap=Marshal.AllocHGlobal(Marshal.SizeOf(c)); Marshal.StructureToPtr(c,cap,false); Check(UpdateProcThreadAttribute(list,0,(IntPtr)0x20009,cap,(IntPtr)Marshal.SizeOf(c),IntPtr.Zero,IntPtr.Zero),"security capabilities attribute");
   jobptr=Marshal.AllocHGlobal(IntPtr.Size); Marshal.WriteIntPtr(jobptr,job); Check(UpdateProcThreadAttribute(list,0,(IntPtr)0x2000D,jobptr,(IntPtr)IntPtr.Size,IntPtr.Zero,IntPtr.Zero),"job list attribute");
   handleptr=Marshal.AllocHGlobal(IntPtr.Size*3); for(int i=0;i<3;i++) Marshal.WriteIntPtr(handleptr,i*IntPtr.Size,std[i]); Check(UpdateProcThreadAttribute(list,0,(IntPtr)0x20002,handleptr,(IntPtr)(IntPtr.Size*3),IntPtr.Zero,IntPtr.Zero),"handle list attribute");
   StartupEx startup=new StartupEx(); startup.startup.cb=Marshal.SizeOf(startup); startup.startup.flags=0x100; startup.startup.input=std[0]; startup.startup.output=std[1]; startup.startup.error=std[2]; startup.attrs=list;
   var command=new StringBuilder(); for(int i=1;i<args.Length;i++) { if(i>1) command.Append(' '); command.Append(Quote(args[i])); }
   Check(CreateProcessW(args[1],command,IntPtr.Zero,IntPtr.Zero,true,0x80004,IntPtr.Zero,System.IO.Path.GetDirectoryName(args[1]),ref startup,out pi),"CreateProcessW");
   for(int i=0;i<3;i++) { CloseHandle(std[i]); std[i]=IntPtr.Zero; }
   Check(OpenProcessToken(pi.process,8,out token),"OpenProcessToken"); int needed; buf=Marshal.AllocHGlobal(4); Check(GetTokenInformation(token,29,buf,4,out needed),"TokenIsAppContainer"); if(Marshal.ReadInt32(buf)!=1) throw new Exception("Target token is not AppContainer"); Marshal.FreeHGlobal(buf); buf=IntPtr.Zero;
   GetTokenInformation(token,30,IntPtr.Zero,0,out needed); if(needed<4) throw new Exception("TokenCapabilities size unavailable"); buf=Marshal.AllocHGlobal(needed); Check(GetTokenInformation(token,30,buf,needed,out needed),"TokenCapabilities"); if(Marshal.ReadInt32(buf)!=0) throw new Exception("Target token has capabilities");
	   Console.Error.WriteLine("[offline-token] appcontainer=1 capabilities=0 pid="+pi.pid);
	   Check(ResumeThread(pi.thread)!=0xffffffff,"ResumeThread"); Check(WaitForSingleObject(pi.process,0xffffffff)==0,"WaitForSingleObject"); uint exit; Check(GetExitCodeProcess(pi.process,out exit),"GetExitCodeProcess"); return unchecked((int)exit);
  } catch(Exception e) { Console.Error.WriteLine("OfflineLauncher: "+e.Message); return 255; }
  finally { if(buf!=IntPtr.Zero) Marshal.FreeHGlobal(buf); if(token!=IntPtr.Zero) CloseHandle(token); if(pi.thread!=IntPtr.Zero) CloseHandle(pi.thread); if(pi.process!=IntPtr.Zero) CloseHandle(pi.process); if(job!=IntPtr.Zero) CloseHandle(job); foreach(IntPtr h in std) if(h!=IntPtr.Zero) CloseHandle(h); if(initialized) DeleteProcThreadAttributeList(list); if(list!=IntPtr.Zero) Marshal.FreeHGlobal(list); if(cap!=IntPtr.Zero) Marshal.FreeHGlobal(cap); if(jobptr!=IntPtr.Zero) Marshal.FreeHGlobal(jobptr); if(handleptr!=IntPtr.Zero) Marshal.FreeHGlobal(handleptr); if(sid!=IntPtr.Zero) LocalFree(sid); }
 }
}
