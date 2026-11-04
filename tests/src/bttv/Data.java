package bttv;
public class Data {
 public static Object ctx=new Object();
 public static int currentBroadcasterId=-1;
 public static int changes=0;
 public static void setCurrentBroadcasterId(int id){currentBroadcasterId=id;changes++;}
}
