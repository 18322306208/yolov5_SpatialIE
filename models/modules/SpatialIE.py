import torch
import torch.nn as nn
import torch.nn.functional as F
import numbers
from einops import rearrange
from einops.layers.torch import Rearrange
import sys
sys.path.append(r"yolov5-upload")
from models.modules.KAN import *

__all__ = ['SpatialIE']

class RFAConv(nn.Module):  # 基于Group Conv实现的RFAConv
    def __init__(self, in_channel, out_channel, kernel_size=3, stride=1):
        super().__init__()
        self.kernel_size = kernel_size
        self.get_weight = nn.Sequential(nn.AvgPool2d(kernel_size=kernel_size, padding=kernel_size // 2, stride=stride),
                                        nn.Conv2d(in_channel, in_channel * (kernel_size ** 2), kernel_size=1,
                                                  groups=in_channel, bias=False))
        self.generate_feature = nn.Sequential(
            nn.Conv2d(in_channel, in_channel * (kernel_size ** 2), kernel_size=kernel_size, padding=kernel_size // 2,
                      stride=stride, groups=in_channel, bias=False),
            nn.BatchNorm2d(in_channel * (kernel_size ** 2)),
            nn.ReLU())
        self.conv = nn.Sequential(nn.Conv2d(in_channel, out_channel, kernel_size=kernel_size, stride=kernel_size),
                                  nn.BatchNorm2d(out_channel),
                                  nn.ReLU())

    def forward(self, x):
        b, c = x.shape[0:2]
        weight = self.get_weight(x)
        h, w = weight.shape[2:]
        weighted = weight.view(b, c, self.kernel_size ** 2, h, w).softmax(2)  # b c*kernel**2,h,w ->  b c k**2 h w
        feature = self.generate_feature(x).view(b, c, self.kernel_size ** 2, h, w)  # b c*kernel**2,h,w ->  b c k**2 h w   获得感受野空间特征
        weighted_data = feature * weighted
        conv_data = rearrange(weighted_data, 'b c (n1 n2) h w -> b c (h n1) (w n2)', n1=self.kernel_size,
                              # b c k**2 h w ->  b c h*k w*k
                           n2=self.kernel_size)
        return self.conv(conv_data)

class OverlapPatchEmbed(nn.Module):
    def __init__(self, in_c=3, embed_dim=48, bias=False):
        super(OverlapPatchEmbed, self).__init__()
        self.proj = nn.Conv2d(in_c, embed_dim, kernel_size=3, stride=1, padding=1, bias=bias)
    def forward(self, x):
        x = self.proj(x)
        return x



## Transformer Block
class KANsformer(nn.Module):
    def __init__(self, dim, num_heads, bias):
        super(KANsformer, self).__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = Attention(dim, num_heads, bias = False)
        self.norm2 = nn.LayerNorm(dim)
        self.kan = KAN([dim,64,dim])

    def forward(self, x):
        b, c, h, w = x.shape # bchw
        x1 = x.permute(0, 2, 3, 1).contiguous() #bhwc
        x1 = x1.view(b, -1, c) #b(hw)c
        x1 = self.norm1(x1) #b(hw)c
        x1 = x1.view(b, h, w, c) #bhwc
        x1 = x1.permute(0, 3, 1, 2).contiguous() # bchw
        x = x + self.attn(x1) # bchw
        b2, c2, h2, w2 = x.shape # bchw
        x2 = x.permute(0, 2, 3, 1).contiguous() #bhwc
        x2 = x2.view(b2, -1, c2) #b(hw)c
        x2 = self.norm2(x2) #b(hw)c
        x2 = x2.view(b2, h2, w2, c2) #b(hw)c
        x2 = x2.view(-1,c2)
        x2 = self.kan(x2)
        x2 = x2.view(b2, h2, w2, c2)
        x2 = x2.permute(0, 3, 1, 2).contiguous()
        x2 = x + x2

        return x2


class Mlp(nn.Module):

    """
    MLP as used in Vision Transformer, MLP-Mixer and related networks
    """

    def __init__(self, in_features, hidden_features=None, out_features=None, act_layer=nn.GELU, drop=0.):
        super().__init__()
        out_features = out_features or in_features
        hidden_features = hidden_features or in_features
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.act = act_layer()
        self.fc2 = nn.Linear(hidden_features, out_features)
        self.drop = nn.Dropout(drop)

    def forward(self, x):
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x

    

class TransformerBlockBackbone(nn.Module):
    def __init__(self, dim, num_heads, bias, mlp_ratio=4., act_layer=nn.GELU, drop_ratio = 0):
        super(TransformerBlockBackbone, self).__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = Attention(dim, num_heads, bias = False)
        self.norm2 = nn.LayerNorm(dim)
        #self.kan = KAN([dim,64,dim])
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(in_features=dim, hidden_features=mlp_hidden_dim, act_layer=act_layer, drop=drop_ratio)

    def forward(self, x):
        b, c, h, w = x.shape # bchw
        x1 = x.permute(0, 2, 3, 1).contiguous() #bhwc
        x1 = x1.view(b, -1, c) #b(hw)c
        x1 = self.norm1(x1) #b(hw)c
        x1 = x1.view(b, h, w, c) #bhwc
        x1 = x1.permute(0, 3, 1, 2).contiguous() # bchw
        x = x + self.attn(x1) # bchw
        b2, c2, h2, w2 = x.shape # bchw
        x2 = x.permute(0, 2, 3, 1).contiguous() #bhwc
        x2 = x2.view(b2, -1, c2) #b(hw)c
        x2 = self.mlp(self.norm2(x2)) #b(hw)c
        x2 = x2.view(b2, h2, w2, c2)
        x2 = x2.permute(0, 3, 1, 2).contiguous()
        x2 = x + x2

        return x2  

class Downsample(nn.Module):
    def __init__(self, n_feat):
        super(Downsample, self).__init__()
        self.body = nn.Sequential(nn.Conv2d(n_feat, n_feat // 2, kernel_size=3, stride=1, padding=1, bias=False),
                                  nn.PixelUnshuffle(2))
    def forward(self, x):
        return self.body(x)

class Upsample(nn.Module):
    def __init__(self, n_feat):
        super(Upsample, self).__init__()
        self.body = nn.Sequential(nn.Conv2d(n_feat, n_feat * 2, kernel_size=3, stride=1, padding=1, bias=False),
                                  nn.PixelShuffle(2))
    def forward(self, x):  # (b,c,h,w)
        return self.body(x)  # (b,c/2,h*2,w*2)

class SpatialAttention(nn.Module):
    def __init__(self):
        super(SpatialAttention, self).__init__()
        self.sa = nn.Conv2d(2, 1, 7, padding=3, padding_mode='reflect', bias=True)
    def forward(self, x):  # x:[b,c,h,w]
        x_avg = torch.mean(x, dim=1, keepdim=True)  # (b,1,h,w)
        x_max, _ = torch.max(x, dim=1, keepdim=True)  # (b,1,h,w)
        x2 = torch.cat([x_avg, x_max], dim=1)  # (b,2,h,w)
        sattn = self.sa(x2)  # 7x7conv (b,1,h,w)
        return sattn * x

class ChannelAttention(nn.Module):
    def __init__(self, dim, reduction=8):
        super(ChannelAttention, self).__init__()
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.ca = nn.Sequential(
            nn.Conv2d(dim, dim // reduction, 1, padding=0, bias=True),
            nn.ReLU(inplace=True),  # Relu
            nn.Conv2d(dim // reduction, dim, 1, padding=0, bias=True),
        )
    def forward(self, x):  # x:[b,c,h,w]
        x_gap = self.gap(x)  # [b,c,1,1]
        cattn = self.ca(x_gap)  # [b,c,1,1]
        return cattn * x

class Channel_Shuffle(nn.Module):
    def __init__(self, num_groups):
        super(Channel_Shuffle, self).__init__()
        self.num_groups = num_groups
    def forward(self, x):
        batch_size, chs, h, w = x.shape
        chs_per_group = chs // self.num_groups
        x = torch.reshape(x, (batch_size, self.num_groups, chs_per_group, h, w))
        # (batch_size, num_groups, chs_per_group, h, w)
        x = x.transpose(1, 2)  # dim_1 and dim_2
        out = torch.reshape(x, (batch_size, -1, h, w))
        return out


class TransformerBlock(nn.Module):
    def __init__(self, dim, num_heads, ffn_expansion_factor, bias, LayerNorm_type):
        super(TransformerBlock, self).__init__()
        self.norm1 = LayerNorm(dim, LayerNorm_type)
        self.attn = Attention(dim, num_heads, bias)
        self.norm2 = LayerNorm(dim, LayerNorm_type)
        self.ffn = FeedForward(dim, ffn_expansion_factor, bias)

    def forward(self, x):
        x = x + self.attn(self.norm1(x1))
        x = x + self.ffn(self.norm2(x1))
        return x

def to_3d(x):
    return rearrange(x, 'b c h w -> b (h w) c')

def to_4d(x, h, w):
    return rearrange(x, 'b (h w) c -> b c h w', h=h, w=w)

class BiasFree_LayerNorm(nn.Module):
    def __init__(self, normalized_shape):
        super(BiasFree_LayerNorm, self).__init__()
        if isinstance(normalized_shape, numbers.Integral):
            normalized_shape = (normalized_shape,)
        normalized_shape = torch.Size(normalized_shape)
        assert len(normalized_shape) == 1
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.normalized_shape = normalized_shape

    def forward(self, x):
        sigma = x.var(-1, keepdim=True, unbiased=False)
        return x / torch.sqrt(sigma + 1e-5) * self.weight


class WithBias_LayerNorm(nn.Module):
    def __init__(self, normalized_shape):
        super(WithBias_LayerNorm, self).__init__()
        if isinstance(normalized_shape, numbers.Integral):
            normalized_shape = (normalized_shape,)
        normalized_shape = torch.Size(normalized_shape)
        assert len(normalized_shape) == 1
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.normalized_shape = normalized_shape
    def forward(self, x):
        device = x.device
        mu = x.mean(-1, keepdim=True)
        sigma = x.var(-1, keepdim=True, unbiased=False)
        result = (x - mu) / torch.sqrt(sigma + 1e-5) * self.weight.to(device) + self.bias.to(device)
        return result


class LayerNorm(nn.Module):
    def __init__(self, dim, LayerNorm_type):
        super(LayerNorm, self).__init__()
        if LayerNorm_type == 'BiasFree':
            self.body = BiasFree_LayerNorm(dim)
        else:
            self.body = WithBias_LayerNorm(dim)
    def forward(self, x):
        h, w = x.shape[-2:]
        return to_4d(self.body(to_3d(x)), h, w)


class FeedForward(nn.Module):
    def __init__(self, dim, ffn_expansion_factor, bias):
        super(FeedForward, self).__init__()
        hidden_features = int(dim * ffn_expansion_factor)
        self.project_in = nn.Conv2d(dim, hidden_features * 2, kernel_size=1, bias=bias)
        self.dwconv = nn.Conv2d(hidden_features * 2, hidden_features * 2, kernel_size=3, stride=1, padding=1,
                                groups=hidden_features * 2, bias=bias)
        self.project_out = nn.Conv2d(hidden_features, dim, kernel_size=1, bias=bias)
    def forward(self, x):
        device = x.device
        self.project_in = self.project_in.to(device)
        self.dwconv = self.dwconv.to(device)
        self.project_out = self.project_out.to(device)
        x = self.project_in(x)
        x1, x2 = self.dwconv(x).chunk(2, dim=1)
        x = F.gelu(x1) * x2
        x = self.project_out(x)
        return x


class Attention(nn.Module):
    def __init__(self, dim, num_heads, bias):
        super(Attention, self).__init__()
        self.num_heads = num_heads
        self.temperature = nn.Parameter(torch.ones(num_heads, 1, 1, dtype=torch.float32), requires_grad=True)
        self.qkv = nn.Conv2d(dim, dim * 3, kernel_size=1, bias=bias)
        self.qkv_dwconv = nn.Conv2d(dim * 3, dim * 3, kernel_size=3, stride=1, padding=1, groups=dim * 3,
                                    bias=bias)
        self.project_out = nn.Conv2d(dim, dim, kernel_size=1, bias=bias)

    def forward(self, x):
        b, c, h, w = x.shape
        device = x.device
        self.qkv = self.qkv.to(device)
        self.qkv_dwconv = self.qkv_dwconv.to(device)
        self.project_out = self.project_out.to(device)
        qkv = self.qkv(x)
        qkv = self.qkv_dwconv(qkv)
        q, k, v = qkv.chunk(3, dim=1)
        q = rearrange(q, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        k = rearrange(k, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        v = rearrange(v, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        q = torch.nn.functional.normalize(q, dim=-1)
        k = torch.nn.functional.normalize(k, dim=-1)
        attn = (q @ k.transpose(-2, -1)) * self.temperature.to(device)
        attn = attn.softmax(dim=-1)
        out = (attn @ v)
        out = rearrange(out, 'b head c (h w) -> b (head c) h w', head=self.num_heads, h=h, w=w)
        out = self.project_out(out)
        return out





class resblock(nn.Module):
    def __init__(self, dim):
        super(resblock, self).__init__()
        self.body = nn.Sequential(nn.Conv2d(dim, dim, kernel_size=3, stride=1, padding=1, bias=False),
                                  nn.PReLU(),
                                  nn.Conv2d(dim, dim, kernel_size=3, stride=1, padding=1, bias=False))
    def forward(self, x):
        res = self.body((x))
        res += x
        return res

class LayerNorm(nn.Module):
    def __init__(self, normalized_shape, eps=1e-6, data_format="channels_last"):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.eps = eps
        self.data_format = data_format
        if self.data_format not in ["channels_last", "channels_first"]:
            raise NotImplementedError
        self.normalized_shape = (normalized_shape,)

    def forward(self, x):
        if self.data_format == "channels_last":
            return F.layer_norm(x, self.normalized_shape, self.weight, self.bias, self.eps)
        elif self.data_format == "channels_first":
            u = x.mean(1, keepdim=True)
            s = (x - u).pow(2).mean(1, keepdim=True)
            x = (x - u) / torch.sqrt(s + self.eps)
            x = self.weight[:, None, None] * x + self.bias[:, None, None]
            return x


def get_dwconv(dim, kernel, bias):
    return nn.Conv2d(dim, dim, kernel_size=kernel, padding=(kernel-1)//2 ,bias=bias, groups=dim)

class gnconv(nn.Module):
    def __init__(self, dim, order, gflayer=None, h=14, w=8, s=1.0):
        super().__init__()
        self.order = order
        self.dims = [dim // (2**i) for i in range(order)]
        self.dims.reverse()
        self.proj_in = nn.Conv2d(dim, 2 * dim, 1)
        self.dwconv = get_dwconv(sum(self.dims), 7, True) #这里改卷积核大小
        self.proj_out = nn.Conv2d(dim, dim, 1)
        self.pws = nn.ModuleList(
            [nn.Conv2d(self.dims[i], self.dims[i + 1], 1) for i in range(order - 1)]
        )
        self.scale = s
        print('[gnconv]', order, 'order with dims=', self.dims, 'scale=%.4f' % self.scale)

    def forward(self, x, mask=None, dummy=False):
        B, C, H, W = x.shape
        fused_x = self.proj_in(x)
        pwa, abc = torch.split(fused_x, (self.dims[0], sum(self.dims)), dim=1)
        dw_abc = self.dwconv(abc) * self.scale
        dw_list = torch.split(dw_abc, self.dims, dim=1)
        x = pwa * dw_list[0]
        for i in range(self.order - 1):
            x = self.pws[i](x) * dw_list[i + 1]

        x = self.proj_out(x)
        return x

class GnBlock(nn.Module):
    def __init__(self, dim, order=3, drop_path=0., layer_scale_init_value=1e-6, gnconv=gnconv):
        super().__init__()

        self.norm1 = LayerNorm(dim, eps=1e-6, data_format='channels_first')
        self.gnconv = gnconv(dim,order=order) # depthwise conv
        self.norm2 = LayerNorm(dim, eps=1e-6)
        self.pwconv1 = nn.Linear(dim, 4 * dim) # pointwise/1x1 convs, implemented with linear layers
        self.act = nn.GELU()
        self.pwconv2 = nn.Linear(4 * dim, dim)

        self.gamma1 = nn.Parameter(layer_scale_init_value * torch.ones(dim),
                                    requires_grad=True) if layer_scale_init_value > 0 else None

        self.gamma2 = nn.Parameter(layer_scale_init_value * torch.ones((dim)),
                                    requires_grad=True) if layer_scale_init_value > 0 else None
    def forward(self, x):
        B, C, H, W  = x.shape
        if self.gamma1 is not None:
            gamma1 = self.gamma1.view(C, 1, 1)
        else:
            gamma1 = 1
        x = x + (gamma1 * self.gnconv(self.norm1(x)))
        input = x
        x = x.permute(0, 2, 3, 1) # (N, C, H, W) -> (N, H, W, C)
        x = self.norm2(x)
        x = self.pwconv1(x)
        x = self.act(x)
        x = self.pwconv2(x)
        if self.gamma2 is not None:
            x = self.gamma2 * x
        x = x.permute(0, 3, 1, 2) # (N, H, W, C) -> (N, C, H, W)
        x = input + x
        return x

class DFC(nn.Module):
    def __init__(self, inp, oup, kernel_size=1, stride=1):
        super(DFC, self).__init__()
        #self.avg_pool = nn.AvgPool2d(7, 1, 3)
        self.gate_fn = nn.Sigmoid()
        self.short_conv = nn.Sequential(
            nn.Conv2d(inp, oup, kernel_size, stride, kernel_size // 2, bias=False),
            nn.BatchNorm2d(oup),
            nn.Conv2d(oup, oup, kernel_size=(1, 5), stride=1, padding=(0, 2), groups=oup, bias=False),
            nn.BatchNorm2d(oup),
            nn.Conv2d(oup, oup, kernel_size=(5, 1), stride=1, padding=(2, 0), groups=oup, bias=False),
            nn.BatchNorm2d(oup),
        )
    def forward(self, x):
        original_size = x.shape[-2:]
        res = self.short_conv(F.avg_pool2d(x, kernel_size=2, stride=2))
        res = self.gate_fn(res)
        res = F.interpolate(res, size=original_size, mode='nearest')
        return res

class HSI_DFC(nn.Module):
    def __init__(self, inp):
        super(HSI_DFC, self).__init__()
        self.gnconv_part = GnBlock(inp // 2, 2)
        self.dfc_part = DFC(inp // 2, inp // 2)
        self.post_conv = nn.Conv2d(inp // 2, inp, kernel_size=1)


    def forward(self, x):
        channels = x.shape[1]
        part1, part2 = torch.split(x, channels // 2, dim=1)
        part1 = self.gnconv_part(part1)
        part2 = self.dfc_part(part2)
        y = part1 * part2
        out = y + part1
        out = self.post_conv(out)
        
        return out



#########################################################################

# Chain-of-Thought Prompt Generation Module (CGM)

class CotPromptParaGen(nn.Module):
    def __init__(self, prompt_inch, prompt_size, num_path=3):
        super(CotPromptParaGen, self).__init__()
        # (128,32,32)->(64,64,64)->(32,128,128)
        self.chain_prompts = nn.ModuleList([
            nn.ConvTranspose2d(
                in_channels=prompt_inch if idx == 0 else prompt_inch // (2 ** idx),
                out_channels=prompt_inch // (2 ** (idx + 1)),
                kernel_size=3, stride=2, padding=1
            ) for idx in range(num_path)
        ])
    def forward(self, x):
        prompt_params = []
        prompt_params.append(x)
        for pe in self.chain_prompts:
            x = pe(x)
            prompt_params.append(x)
        return prompt_params


#########################################################################

# Content-driven Prompt Block (CPB)

class ContentDrivenPromptBlock(nn.Module):
    def __init__(self, dim, prompt_dim, reduction=8):
        super(ContentDrivenPromptBlock, self).__init__()
        self.dim = dim
        self.pa2 = nn.Conv2d(2 * dim, dim, 7, padding=3, padding_mode='reflect', groups=dim, bias=True)
        self.sigmoid = nn.Sigmoid()
        self.conv3x3 = nn.Conv2d(prompt_dim, prompt_dim, kernel_size=3, stride=1, padding=1, bias=False)
        self.conv1x1 = nn.Conv2d(dim, prompt_dim, kernel_size=1, stride=1, bias=False)
        self.sa = SpatialAttention()
        self.ca = ChannelAttention(dim, reduction)
        self.myshuffle = Channel_Shuffle(2)
        self.out_conv1 = nn.Conv2d(prompt_dim + dim, dim, kernel_size=1, stride=1, bias=False)
        self.hsi_dfc = HSI_DFC(dim)

    def forward(self, x, prompt_param):
        # latent: (b,dim*8,h/8,w/8)  prompt_param3: (1, 256, 16, 16)
        x_ = x
        B, C, H, W = x.shape
        cattn = self.ca(x)  # channel-wise attn
        sattn = self.sa(x)  # spatial-wise attn
        pattn1 = sattn + cattn
        pattn1 = pattn1.unsqueeze(dim=2)  # [b,c,1,h,w]
        x = x.unsqueeze(dim=2)  # [b,c,1,h,w]
        x2 = torch.cat([x, pattn1], dim=2)  # [b,c,2,h,w]
        x2 = Rearrange('b c t h w -> b (c t) h w')(x2)  # [b,c*2,h,w]
        x2 = self.myshuffle(x2)  # [c1,c1_att,c2,c2_att,...]
        pattn2 = self.pa2(x2)
        pattn2 = self.conv1x1(pattn2)  # [b,prompt_dim,h,w]
        prompt_weight = self.sigmoid(pattn2)  # Sigmod
        prompt_param = F.interpolate(prompt_param, (H, W), mode="bilinear")
        # (b,prompt_dim,prompt_size,prompt_size) -> (b,prompt_dim,h,w)
        prompt = prompt_weight * prompt_param
        prompt = self.conv3x3(prompt)  # (b,prompt_dim,h,w)
        inter_x = torch.cat([x_, prompt], dim=1)  # (b,prompt_dim+dim,h,w)
        inter_x = self.out_conv1(inter_x)  # (b,dim,h,w) dim=64
        inter_x = self.hsi_dfc(inter_x)

        return inter_x



class HalveChannels(nn.Module):
    def __init__(self, in_channels):
        super(HalveChannels, self).__init__()
        self.conv = nn.Conv2d(in_channels, in_channels // 2, kernel_size=1, stride=1, padding=0, bias=False)
    def forward(self, x):
        return self.conv(x)  

class ToRGB(nn.Module):
    def __init__(self, in_channels, out_channels=3):
        super(ToRGB, self).__init__()
        self.conv = nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=1, stride=1, padding=0, bias=False)
    def forward(self, x):
        # 确保卷积层的输入通道数与输入张量的通道数匹配
        if self.conv.in_channels != x.shape[1]:
            self.conv = nn.Conv2d(x.shape[1], 3, kernel_size=1, stride=1, padding=0, bias=False)
        return self.conv(x)


#########################################################################

# SpatialIE

class SpatialIE(nn.Module):
    def __init__(self, c_in=3, c_out=3, dim=4, prompt_inch=128, prompt_size=32):
        super(SpatialIE, self).__init__()
        #self.patch_embed = OverlapPatchEmbed(c_in, dim)
        self.conv0 = RFAConv(c_in, dim)
        self.conv1 = TransformerBlockBackbone(dim, 1, bias=False)
        self.conv2 = TransformerBlockBackbone(dim * 2, 2, bias=False)
        self.conv3 = KANsformer(dim * 4, 4, bias=False)
        self.conv4 = TransformerBlockBackbone(dim * 8, 8, bias=False)
        self.conv5 = TransformerBlockBackbone(dim * 8, 4, bias=False)
        self.conv6 = TransformerBlockBackbone(dim * 4, 2, bias=False)
        self.conv7 = TransformerBlockBackbone(dim * 2, 1, bias=False)
        self.halvechannels1 = HalveChannels(dim * 8)
        self.halvechannels2 = HalveChannels(dim * 4)
        self.toRGB = ToRGB(dim * 4, 3)
        self.down1 = Downsample(dim)
        self.down2 = Downsample(dim * 2)
        self.down3 = Downsample(dim * 4)
        self.prompt_param_ini = nn.Parameter(torch.rand(1, prompt_inch, prompt_size, prompt_size))  # (b,c,h,w)
        self.myPromptParamGen = CotPromptParaGen(prompt_inch=prompt_inch, prompt_size=prompt_size)
        self.prompt1 = ContentDrivenPromptBlock(dim=dim * 2 ** 1, prompt_dim=prompt_inch // 4, reduction=8)  # !!!!
        self.prompt2 = ContentDrivenPromptBlock(dim=dim * 2 ** 2, prompt_dim=prompt_inch // 2, reduction=8)
        self.prompt3 = ContentDrivenPromptBlock(dim=dim * 2 ** 3, prompt_dim=prompt_inch, reduction=8)
        self.up3 = Upsample(dim * 8)
        self.up2 = Upsample(dim * 4)
        self.up1 = Upsample(dim * 2)
    def forward(self, x):  # (b,c_in,h,w)
        prompt_params = self.myPromptParamGen(self.prompt_param_ini)
        prompt_param1 = prompt_params[2]  # [1, 64, 64, 64]
        prompt_param2 = prompt_params[1]  # [1, 128, 32, 32]
        prompt_param3 = prompt_params[0]  # [1, 256, 16, 16]
        #x0 = self.patch_embed(x)  # (b,dim,h,w)
        x0 = self.conv0(x)
        x1 = self.conv1(x0)  # (b,dim,h,w)
        x1_down = self.down1(x1)  # (b,dim,h/2,w/2)
        x2 = self.conv2(x1_down)  # (b,dim,h/2,w/2)
        x2_down = self.down2(x2)
        x3 = self.conv3(x2_down)
        x3_down = self.down3(x3)
        x4 = self.conv4(x3_down)
        device = x4.device
        self.prompt1 = self.prompt1.to(device)
        self.prompt2 = self.prompt2.to(device)
        self.prompt3 = self.prompt3.to(device)
        x4_prompt = self.prompt3(x4, prompt_param3)
        x3_up = self.up3(x4_prompt)
        x5 = self.conv5(torch.cat([x3_up, x3], 1))
        x5 = self.halvechannels1(x5)
        x5_prompt = self.prompt2(x5, prompt_param2)
        x2_up = self.up2(x5_prompt)
        x2_cat = torch.cat([x2_up, x2], 1)
        x6 = self.conv6(x2_cat)
        x6 = self.halvechannels2(x6)
        x6_prompt = self.prompt1(x6, prompt_param1)
        x1_up = self.up1(x6_prompt)
        x7 = self.conv7(torch.cat([x1_up, x1], 1))
        x7 = self.toRGB(x7)

        return x7




if __name__ == "__main__":

    # Generating Sample image
    image_size = (1, 3, 640, 640)
    image = torch.rand(*image_size)
    out = SpatialIE(3, 3, 4)
    out = out(image)
    print(out.size())



