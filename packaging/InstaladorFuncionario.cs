using System;
using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Windows.Forms;
using Microsoft.Win32;

class InstaladorFuncionario : Form {
    static readonly string Destino=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","DeliveryBotFuncionario");
    readonly Button instalar=new Button {Text="Instalar aplicativo do funcionário",Width=310,Height=40,Left=24,Top=155};
    [STAThread] static void Main(){Application.EnableVisualStyles();Application.Run(new InstaladorFuncionario());}
    public InstaladorFuncionario(){
        Text="Instalar DeliveryBot Funcionário";Width=530;Height=265;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
        Controls.Add(new Label {Left=24,Top=22,Width=465,Height=120,Text="Pedidos manuais e caixa do funcionário\n\nO aplicativo usa os dados do responsável pela rede da loja. Depois de instalar, importe o arquivo .dbterminal e entre com sua conta individual de caixa. Python, Node.js e Docker não são necessários.\n\nFeche o aplicativo antes de atualizar."});
        Controls.Add(instalar);instalar.Click+=(s,e)=>Instalar();
    }
    static void Extrair(string nome,string destino){using(var origem=Assembly.GetExecutingAssembly().GetManifestResourceStream(nome)){if(origem==null)throw new Exception("Componente ausente.");using(var saida=File.Create(destino))origem.CopyTo(saida);}}
    static void Atalho(string destino,string exe){var tipo=Type.GetTypeFromProgID("WScript.Shell");var shell=Activator.CreateInstance(tipo);var link=tipo.InvokeMember("CreateShortcut",BindingFlags.InvokeMethod,null,shell,new object[]{destino});link.GetType().InvokeMember("TargetPath",BindingFlags.SetProperty,null,link,new object[]{exe});link.GetType().InvokeMember("WorkingDirectory",BindingFlags.SetProperty,null,link,new object[]{Destino});link.GetType().InvokeMember("Save",BindingFlags.InvokeMethod,null,link,null);}
    void Instalar(){
        instalar.Enabled=false;
        try{
            Directory.CreateDirectory(Destino);
            string exe=Path.Combine(Destino,"DeliveryBot-Funcionario.exe");
            Extrair("aplicativo",exe);Extrair("desinstalador",Path.Combine(Destino,"Desinstalar.exe"));Extrair("icone",Path.Combine(Destino,"DeliveryBot.ico"));
            foreach(var pasta in new[]{Environment.SpecialFolder.DesktopDirectory,Environment.SpecialFolder.Programs})Atalho(Path.Combine(Environment.GetFolderPath(pasta),"DeliveryBot Funcionário.lnk"),exe);
            using(var key=Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\DeliveryBotFuncionario")){
                key.SetValue("DisplayName","DeliveryBot Funcionário");key.SetValue("DisplayVersion","2.47.0");key.SetValue("Publisher","DeliveryBot");key.SetValue("InstallLocation",Destino);key.SetValue("DisplayIcon",Path.Combine(Destino,"DeliveryBot.ico"));key.SetValue("UninstallString","\""+Path.Combine(Destino,"Desinstalar.exe")+"\"");key.SetValue("NoModify",1,RegistryValueKind.DWord);key.SetValue("NoRepair",1,RegistryValueKind.DWord);
            }
            MessageBox.Show("Instalado. Abra DeliveryBot Funcionário e importe o acesso fornecido pelo responsável.","DeliveryBot Funcionário");Close();
        }catch(Exception){MessageBox.Show("Não foi possível instalar. Feche o aplicativo do funcionário e tente novamente.","DeliveryBot Funcionário");instalar.Enabled=true;}
    }
}
